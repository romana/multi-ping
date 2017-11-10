"""
Copyright 2017 Pani Networks Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""

__version__ = "1.0.6"

import socket
import struct
import time

# Packet header operations in Python are most easiest done by using the
# struct package and packing values according to specific formats. For
# the ICMP header the pack format string is this. Note the '!' in the format
# string: This means that all packing/unpacking correctly takes network byte
# order into account.
_ICMP_HDR_PACK_FORMAT = "!BBHHH"

# Some offsets we use when extracting data from the header
_ICMP_HDR_OFFSET      = 20
_ICMP_ID_OFFSET       = _ICMP_HDR_OFFSET + 4
_ICMP_PAYLOAD_OFFSET  = _ICMP_HDR_OFFSET + 8


class MultiPingError(Exception):
    """
    Exception class for the multiping package.

    """
    pass


class MultiPing(object):

    def __init__(self, dest_addrs, sock=None):
        """
        Initialize a new multi ping object. This takes the configuration
        consisting of the list of destination addresses and an optional socket
        parameter. If no socket is provided, it will be created.

        A 'ping' (ICMPEcho) request is sent to all the specified IP addresses
        by calling the send() method. Results can be colleced via the receive()
        method, which can be called multiple times to see if any further
        results may have arrived.

        Another call to send() creates a new batch of pings to any addresses
        for which we have not received results, yet.

        """
        # Perform some sanity checking
        if len(dest_addrs) > 65535:
            # The ID field is only 16 bits wide, so we can't possibly send out
            # more than 2^16 requests at the same time without rolling over
            # onto our own IDs.
            raise MultiPingError("Cannot send ICMP echo request to more than "
                                 "65535 addresses at the same time.")

        self._dest_addrs      = [socket.gethostbyname(d) for d in dest_addrs]
        self._id_to_addr      = {}
        self._remaining_ids   = None
        self._last_used_id    = None
        self._time_stamp_size = struct.calcsize("d")

        self._receive_has_been_called = False

        # Open an ICMP socket, if we weren't provided with one already
        if sock:
            self._sock = sock
        else:
            self._sock = self._open_icmp_socket()

    def _open_icmp_socket(self):
        """
        Opens a socket suitable for sending/receiving ICMP echo
        requests/responses.

        """
        try:
            return socket.socket(socket.AF_INET, socket.SOCK_RAW,
                                 socket.IPPROTO_ICMP)
        except socket.error as e:
            if e.errno == 1:
                raise MultiPingError("Root privileges required for sending "
                                     "ICMP")
            # Re-raise any other error
            raise

    def _checksum(self, msg):
        """
        Calculate the checksum of a packet.

        This is inspired by a response on StackOverflow here:
        https://stackoverflow.com/a/1769267/7242672

        Thank you to StackOverflow user Jason Orendorff.

        """
        def carry_around_add(a, b):
            c = a + b
            return (c & 0xffff) + (c >> 16)

        s = 0
        for i in range(0, len(msg), 2):
            w = (msg[i] << 8) + msg[i + 1]
            s = carry_around_add(s, w)
        s = ~s & 0xffff

        return s

    def _send_ping(self, dest_addr, payload):
        """
        Send a single ICMPecho (ping) packet to the specified address.

        The payload must be specified as a packed byte string. Note that its
        length has to be divisible by 2 for this to work correctly.

        """
        pkt_id = self._last_used_id

        # For checksum calculation we require a dummy header, with the checksum
        # field set to zero. This header consists of:
        # - ICMP type = 8 (unsigned byte)
        # - ICMP code = 0 (unsigned byte)
        # - checksum  = 0 (unsigned short)
        # - packet id     (unsigned short)
        # - sequence  = 0 (unsigned short)  This doesn't have to be 0.
        dummy_header = bytearray(struct.pack(_ICMP_HDR_PACK_FORMAT,
                                             8, 0, 0, pkt_id, 0))

        # Calculate the checksum over the combined dummy header and payload
        checksum = self._checksum(dummy_header + payload)

        # We can now create the real header, which contains the correct
        # checksum. Need to make sure to convert checksum to network byte
        # order.
        real_header = bytearray(struct.pack(_ICMP_HDR_PACK_FORMAT,
                                            8, 0, checksum, pkt_id, 0))

        # Full packet consists of header plus payload
        full_pkt = real_header + payload

        # The full address for a sendto operation consists of the IP address
        # and a port. We don't really need a port for ICMP, so we just use 0
        # for that.
        full_dest_addr = (dest_addr, 0)

        self._sock.sendto(full_pkt, full_dest_addr)

    def send(self):
        """
        Send pings to multiple addresses, ensuring unique IDs for each request.

        This operation is non-blocking. Use 'receive' to get the results.

        Send can be called multiple times. If there are any addresses left from
        the previous send, from which results have not been received yet, then
        it will resend pings to those remaining addresses.

        """
        # Collect all the addresses for which we have not seen responses yet.
        if not self._receive_has_been_called:
            all_addrs = self._dest_addrs
        else:
            all_addrs = [a for (i, a) in list(self._id_to_addr.items())
                         if i in self._remaining_ids]

        if self._last_used_id is None:
            # Will attempt to continue at the last request ID we used. But if
            # we never sent anything before then we create a first ID
            # 'randomly' from the current time. ID is only a 16 bit field, so
            # need to trim it down.
            self._last_used_id = int(time.time()) & 0xffff

        # Send ICMPecho to all addresses...
        for addr in all_addrs:
            # Make a unique ID, wrapping around at 65535.
            self._last_used_id = (self._last_used_id + 1) & 0xffff
            # Remember the address for each ID so we can produce meaningful
            # result lists later on.
            self._id_to_addr[self._last_used_id] = addr
            # Send an ICMPecho request packet. We specify a payload consisting
            # of the current time stamp. This is returned to us in the
            # response and allows us to calculate the 'ping time'.
            self._send_ping(addr, payload=struct.pack("d", time.time()))

    def _read_all_from_socket(self, timeout):
        """
        Read all packets we currently can on the socket.

        Returns list of tuples. Each tuple contains a packet and the time at
        which it was received. NOTE: The receive time is the time when our
        recv() call returned, which greatly depends on when it was called. The
        time is NOT the time at which the packet arrived at our host, but it's
        the closest we can come to the real ping time.

        If nothing was received within the timeout time, the return list is
        empty.

        First read is blocking with timeout, so we'll wait at least that long.
        Then, in case any more packets have arrived, we read everything we can
        from the socket in non-blocking mode.

        """
        pkts = []
        try:
            self._sock.settimeout(timeout)
            while True:
                p = self._sock.recv(64)
                # Store the packet and the current time
                pkts.append((bytearray(p), time.time()))
                # Continue the loop to receive any additional packets that
                # may have arrived at this point. Changing the socket to
                # non-blocking (by setting the timeout to 0), so that we'll
                # only continue the loop until all current packets have been
                # read.
                self._sock.settimeout(0)
        except socket.timeout:
            # In the first blocking read with timout, we may not receive
            # anything. This is not an error, it just means no data was
            # available in the specified time.
            pass
        except socket.error as e:
            # When we read in non-blocking mode, we may get this error with
            # errno 11 to indicate that no more data is available. That's ok,
            # just like the timeout.
            if e.errno == 11 or e.errno == 10035:
                pass
            else:
                # We're not expecting any other socket exceptions, so we
                # re-raise in that case.
                raise

        return pkts

    def receive(self, timeout):
        """
        Receive ping responses from the socket. Attempts to read responses for
        all stored IDs (as generated by send()).

        Returns a tuple with a dict and a list:

        - Dict contains IP addresses for which we received a response and the
          time
        - List contains IP addresses for which we have not received a response,
          yet

        """
        if not self._id_to_addr:
            raise MultiPingError("No requests have been sent, yet.")

        self._receive_has_been_called = True

        # Continue with any remaining IDs for which we hadn't received an
        # answer, yet...
        if self._remaining_ids is None:
            # ... but if we don't have any stored yet, then we are just calling
            # receive() for the first time afer a send. We initialize
            # the list of expected IDs from all the IDs we created during the
            # send().
            self._remaining_ids = list(self._id_to_addr.keys())

        if len(self._remaining_ids) == 0:
            raise MultiPingError("No responses pending")

        remaining_time = timeout
        results        = {}

        # Keep looping until we either have responses for all request IDs, or
        # no more time is left.
        while self._remaining_ids and remaining_time > 0:
            start_time = time.time()
            pkts = self._read_all_from_socket(remaining_time)

            for pkt, resp_receive_time in pkts:
                # Extract the ICMP ID of the response
                pkt_id = (pkt[_ICMP_ID_OFFSET] << 8) + pkt[_ICMP_ID_OFFSET + 1]

                if pkt_id in self._remaining_ids:
                    # The sending timestamp was encoded in the echo request
                    # body and is now returned to us in the response. Note that
                    # network byte order doesn't matter here, since we get
                    # exactly the order of bytes back that we originally sent
                    # from this host.
                    payload = pkt[_ICMP_PAYLOAD_OFFSET:]
                    req_sent_time = struct.unpack(
                            "d", payload[:self._time_stamp_size])[0]
                    results[self._id_to_addr[pkt_id]] = \
                             resp_receive_time - req_sent_time

                    self._remaining_ids.remove(pkt_id)

            # Calculate how much of the available overall timeout time is left
            end_time = time.time()
            remaining_time = remaining_time - (end_time - start_time)

        return (results, [self._id_to_addr[i] for i in self._remaining_ids])


def multi_ping(dest_addrs, timeout, retry=0):
    """
    Combine send and receive measurement into single function.

    This offers a retry mechanism: Overall timeout time is divided by
    number of retries. Additional ICMPecho packets are sent to those
    addresses from which we have not received answers, yet.

    The retry mechanism is useful, because individual ICMP packets may get
    lost.

    If 'retry' is set to 0 then only a single packet is sent to each
    address.

    """
    retry = int(retry)
    if retry < 0:
        retry = 0

    timeout = float(timeout)
    if timeout < 0.1:
        raise MultiPingError("Timeout < 0.1 seconds not allowed")

    retry_timeout = float(timeout) / (retry + 1)
    if retry_timeout < 0.1:
        raise MultiPingError("Time between ping retries < 0.1 seconds")

    mp = MultiPing(dest_addrs)

    results = {}
    retry_count = 0
    while retry_count <= retry:
        # Send a batch of pings
        mp.send()
        single_results, no_results = mp.receive(retry_timeout)
        # Add the results from the last sending of pings to the overall results
        results.update(single_results)
        if not no_results:
            # No addresses left? We are done.
            break
        retry_count += 1

    return results, no_results
