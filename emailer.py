#!/usr/bin/env python
"""
Open Web Foundation random number emailer. This program generates a random 
token for each email address in a recipients list, then sends each recipient
an email containing their random token.

Once everyone has been emailed, the list of random tokens is shuffled and 
printed to stdout in a random order. Feel free to redirect stdout to a file.

Example: ./emailer.py -H smtp.gmail.com -P 587 --tls -u <email> -p <password> <email>@gmail.com
"""

import smtplib
import random
import sys
from optparse import OptionParser
from email.mime.text import MIMEText

DEFAULT_TEMPLATE = 'template.txt'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 1025
DEFAULT_RECIPIENTS = 'recipients.txt'

RANDOM_STRING_LENGTH = 64
RANDOM_STRING_ALPHABET = 'abcdefghjklmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789' 


def random_token(length=RANDOM_STRING_LENGTH, alphabet=RANDOM_STRING_ALPHABET):
    "Generate a random string with the given length and alphabet."
    return ''.join(random.choice(alphabet) for _ in xrange(length))


def render_body(template, context):
    """Replaces {{ <var> }} with the value of that variable from 
    the context."""
    for key, value in context.iteritems():
        template = template.replace('{{ %s }}' % key, value)
    return template


def parse_template(template):
    """Parses the template file, removes comments, and returns the 
    subject and the body."""

    # Remove comments, get subject & body.
    try:
        fd = open(template)
        lines = [line for line in fd.readlines() if not line.startswith('#')]
    finally:
        fd.close()

    subject, body = lines[0], lines[1:]

    # Strip leading blank lines from body
    while not body[0].strip(): 
        body.pop(0)

    return subject, ''.join(body)


def get_recipients(recipients):
    "Parse the recipients file and return a list of recipients."
    try:
        fd = open(recipients)
        return [recipient.strip() for recipient in fd.readlines() if recipient.strip()]
    finally:
        fd.close()


def main(template, sender, recipients, host, port, tls=False, username=None, password=None):
    subject, body = parse_template(template)

    print >>sys.stderr, 'Connecting to SMTP server %s:%d...' % (host, port)
    s = smtplib.SMTP(host, port)
    if tls:
        print >>sys.stderr, 'Using TLS...'
        s.ehlo()
        s.starttls()
        s.ehlo()
    if not (username is None or password is None):
        print >>sys.stderr, 'Sending credentials...'
        try:
            s.login(username, password)
        except smtplib.SMTPAuthenticationError, ex:
            print >>sys.stderr, 'Authorization failed.'
            print >>sys.stderr, '%s: %s' % (ex.smtp_code, ex.smtp_error)
            print >>sys.stderr, 'Bailing.'
            sys.exit(1)

    random_tokens = []
    for recipient in get_recipients(recipients):
        token = random_token()
        random_tokens.append(token)
        context = {
            'from_email': sender,
            'email': recipient,
            'random_token': token,
        }
        msg = MIMEText(render_body(body, context))
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject 
        print >>sys.stderr, 'Sending email to "%s"...' % recipient
        s.sendmail(sender, [recipient], msg.as_string())
    print >>sys.stderr, 'All done. Sending random numbers to stdout.'

    # Shuffle 'em up so they can't be re-associated later.
    random.shuffle(random_tokens)
    for token in random_tokens:
        print token

    print >>sys.stderr, 'Bye!'
    s.quit()


def sandbox(localhost, localport, remotehost, remoteport):
    import asyncore
    from smtpd import DebuggingServer
    server = DebuggingServer((localhost, localport), (remotehost, remoteport))
    print >>sys.stderr, 'Sandbox SMTP server started.'
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    parser = OptionParser('usage: %prog [options] from_address', description=__doc__.strip())
    parser.add_option('-H', '--host', dest='host', help='SMTP server hostname', default=DEFAULT_HOST)
    parser.add_option('-P', '--port', dest='port', type='int', help='SMTP server port', default=DEFAULT_PORT)
    parser.add_option('-T', '--tls', dest='tls', action='store_true', help='Use TLS to connect to the SMTP server')
    parser.add_option('-u', '--user', dest='username', help='Username for SMTP server login')
    parser.add_option('-p', '--pass', dest='password', help='Password for SMTP server login')
    parser.add_option('-t', '--template', dest='template', help='E-mail template', default=DEFAULT_TEMPLATE)
    parser.add_option('-r', '--recipients', dest='recipients', help='File containing email recipients (one per line)', default=DEFAULT_RECIPIENTS)
    parser.add_option('-s', '--sandbox', dest='sandbox', action='store_true', help='Run in sandbox mode, print emails to stdout instead of sending them')

    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.error('incorrect number of arguments')

    if options.sandbox:
        print >>sys.stderr, 'Starting sandbox SMTP server...'
        import os
        import time
        pid = os.fork()
        if pid == 0:
            sandbox('localhost', 8025, 'localhost', 25)
        else:
            time.sleep(3) # Give the SMTP server a second to start up

        # Reset options to work with the sandbox.
        options.host = 'localhost'
        options.port = 8025
        options.tls = False
        options.username = None
        options.password = None

    main(options.template, args[0], options.recipients, options.host, 
         options.port, options.tls, options.username, options.password)

    if options.sandbox:
        import signal
        print >>sys.stderr, 'Terminating sandbox SMTP server...'
        os.kill(pid, signal.SIGHUP)
        print >>sys.stderr, 'Waiting for SMTP server to go away...'
        os.wait()
        print >>sys.stderr, 'Bye for realz.'
