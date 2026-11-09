from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend


class PlainConsoleEmailBackend(ConsoleEmailBackend):
    """Dev-only console backend that prints the body as plain text.

    The stock console backend prints the MIME-encoded message. Long lines such as reset links get
    quoted-printable soft breaks ("=" at the end of a line), so a link copied from the terminal is
    cut short and Django reports it as expired.
    """

    def write_message(self, message):
        self.stream.write(f"To: {', '.join(message.to)}\nSubject: {message.subject}\n\n{message.body}\n{'-' * 79}\n")
