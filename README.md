# MultiPing: A pure-python implemention to monitor IP addresses with pings

MultiPing is a Python library to monitor one or many IP addresses via ICMP echo
(ping) requests. Features:

* It works for Python 2 and 3.
* Supports timeouts and retries.
* Supports IPv4 as well as IPv6.
* Small and compact and does not rely on any 3rd party packages, aside from
  what's included in Python.

It is ideally suited to monitor large numbers of hosts in clusters, but is just
as suitable to check on a single address.

MultiPing was originally developed for the
[vpc-router](https://github.com/romana/vpc-router) project, but can easily
be used on its own.

## Installation

### Installation via pip

MultiPing is available in PyPi, the Python Package Index. Therefore, you can
install it simply with:

    pip install multiping

### Installation from source

After downloading the code or cloning this repository, please run the `setup.py`
file, which is included in the source code:

    python setup.py install

## Contributions

We welcome any contributions, bug reports or feedback. Please use our
[issue tracker](https://github.com/romana/multi-ping/issues) to file bugs or
request additional features. We are happy to consider pull requests as well.

## Using MultiPing

_Note: ICMP packets can only be sent by processes with root privileges._

Here is an example of how to use MultiPing in your own code:

    from multiping import MultiPing

    # Create a MultiPing object to test three hosts / addresses
    mp = MultiPing(["8.8.8.8", "youtube.com", "127.0.0.1"
                    "2001:4860:4860::8888"])

    # Send the pings to those addresses
    mp.send()

    # With a 1 second timout, wait for responses (may return sooner if all
    # results are received).
    responses, no_responses = mp.receive(1)

The `receive()` function returns a tuple containing a results dictionary
(addresses and response times) as well as a list of addresses that did not
respond in time. The results may be processed like this:

    ...

    for addr, rtt in responses.items():
        print "%s responded in %f seconds" % (addr, rtt)

    if no_responses:
        print "These addresses did not respond: %s" % ", ".join(no_responses)
        # Sending pings once more, but just to those addresses that have not
        # responded, yet. The MultiPing object 'mp' remembers the state of
        # which address has responded already, so that another call to
        # send() just generates packets to those hosts from which we haven't
        # heard back, yet.
        mp.send()
        responses, no_responses = mp.receive(1)

        ...

Note that `send()` can be called multiple times. If there are any addresses
left for which no response has been received yet then this will resend pings
to those remaining addresses.

A convenient `multi_ping()` function is provided, which implements retries and
delivers results in a single and simple function call:

    from multiping import multi_ping

    addrs = ["8.8.8.8", "youtube.com", "127.0.0.1", "2001:4860:4860::8888"]

    # Ping the addresses up to 4 times (initial ping + 3 retries), over the
    # course of 2 seconds. This means that for those addresses that do not
    # respond another ping will be sent every 0.5 seconds.
    responses, no_responses = multi_ping(addrs, timeout=2, retry=3)

Also see the `demo.py` file for more examples.

If there are any names or addresses in the list of target addresses, which
cannot be resolved or looked up, a `socket.gaierror` is raised. This can be
surpressed if the `silent_lookup_errors` parameter flag is set. Either as named
parameter for the `multi_ping` function or when a `MultiPing` object is
created.

