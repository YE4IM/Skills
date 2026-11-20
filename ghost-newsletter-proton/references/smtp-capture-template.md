# SMTP capture template (generic, not executed)

This is a generic, offline-safe template for an isolated STARTTLS capture
sink. **It has not been executed as part of this skill package.** Review,
adapt, and test it in a private lab before use. Do not treat this file as a
previously run fixture, and do not call unpublished scripts that are not in
this package.

## Requirements

- Bind only on an internal Docker network or loopback alias. Do not publish
  the listener on a public address.
- Offer STARTTLS and require the proxy to use `require_tls` with peer and
  hostname verification enabled.
- Use a certificate whose DNS SAN matches the hostname in the proxy
  `MAIL_URL`. Mount the CA into the proxy with the selected runtime's
  supported trust interface (for PHP, `openssl.cafile`).
- Correlate captured messages by unique subject and, when present,
  `X-Proxy-Trace` or `X-Newsletter-Delivery-Id`.
- For a pass, require exactly one captured message for that unique test, with
  exactly one legal, bracketed MIME `Message-Id`.
- Do not send captured copies onward. Use reserved `.test` identities.

## Minimal listener sketch

The following sketch is illustrative. It is not a complete production
service, and it was not used as a recorded acceptance fixture.

```python
#!/usr/bin/env python3
"""TEMPLATE ONLY. Review before use. Not executed with this skill package."""
import ssl
from pathlib import Path
from aiosmtpd.controller import Controller  # add only after local review
from aiosmtpd.smtp import SMTP as SMTPProtocol

class CaptureHandler:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(mode=0o700, exist_ok=True)

    async def handle_DATA(self, server, session, envelope):
        unique = [line for line in envelope.content.splitlines()
                  if line.lower().startswith(b'subject:')]
        # Persist the raw MIME message and inspect Message-Id separately.
        dest = self.output_dir / 'capture.eml'
        dest.write_bytes(envelope.content)
        return '250 OK'

def main():
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain('capture-cert.pem', 'capture-key.pem')
    handler = CaptureHandler(Path('./captures'))
    controller = Controller(
        handler,
        hostname='smtp.example.test',
        port=2525,
        tls_context=context,
        require_starttls=True,
    )
    controller.start()
    print('template listener is a sketch; do not assume it is running')

if __name__ == '__main__':
    main()
```

Replace hostnames, paths, and certificate files with values from the isolated
lab. Confirm STARTTLS is advertised before pointing the proxy at the sink.
If a dependency such as `aiosmtpd` is not already present, install it only in
the lab environment after review; this skill's local Python tests must not
import or start this template.
