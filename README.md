# MultiPing: A pure-python implemention to monitor IP addresses with pings

MultiPing is a Python library to monitor one or many IP addresses via ICMP echo
(ping) requests. It works for Python 2 and 3, supports timeouts and retries, is
small and compact and does not rely on any 3rd party packages, aside from
what's included in Python.

It is ideally suited to monitor large numbers of hosts in clusters, but is just
as suitable to check on a single address.

MultiPing was developed for the
[vpc-router](https://github.com/romana/vpc-router) project, but can be used
on its own.

## Installation

After downloading the code, please run the `setup.py` file, which is included
in the source code:

    python setup.py install

### Inclusion in other projects

If you wish to use MultiPing in your own project, you should add this line to
your `requirements` file:

    -e git+git://github.com/romana/multi-ping#egg=multiping

In your own `setup.py` file, you should add:

    ...

    install_requires = [
        ...

        'multiping==1.0.0',

        ...
    ],
    dependency_links = [
        ...

        "https://github.com/romana/multi-ping/tarball/master#egg=multiping-1.0.0",

        ...
    ],

    ...

## Using MultiPing

_Note: ICMP packets can only be sent by processes with root privileges._

Here is an example of how to use MultiPing in your own code:

    from multiping import MultiPing

    # Create a MultiPing object to test three hosts / addresses
    mp = MultiPing(["8.8.8.8", "youtube.com", "127.0.0.1"])

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
        # responded, yet.
        mp.send()
        responses, no_responses = mp.receive(1)

        ...

Note that `send()` can be called multiple times. If there are any addresses
left for which no response has been received yet then this will resend pings
to those remaining addresses.

A convenient `multi_ping()` function is provided, which implements retries and
delivers results in a single function call:

    from multiping import multi_ping

    addrs = ["8.8.8.8", "youtube.com", "127.0.0.1"]

    # Ping the addresses up to 4 times (initial ping + 3 retries), over the
    # course of 2 seconds. This means that for those addresses that do not
    # respond another ping will be sent every 0.5 seconds.
    responses, no_responses = multi_ping(addrs, 2, 3)

Also see the `demo.py` file for more examples.

