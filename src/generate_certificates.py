import os
from OpenSSL import crypto


def generate_self_signed_cert(cert_file, key_file):
    """Generate a self-signed certificate if it doesn't exist"""
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("SSL certificates already exist")
        return False

    print("Generating self-signed SSL certificate...")

    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    cert = crypto.X509()
    cert.get_subject().C = "US"  # you can change this stuff if you'd like
    cert.get_subject().ST = "State"
    cert.get_subject().L = "City"
    cert.get_subject().O = "Organization"
    cert.get_subject().OU = "Organizational Unit"
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(
        365 * 24 * 60 * 60
    )  # server https cert only valid for a year lol
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, "sha256")

    with open(cert_file, "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    with open(key_file, "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

    print(f"SSL certificate generated: {cert_file}")
    print(f"SSL key generated: {key_file}")
    return True


if __name__ == "__main__":
    current_working_dir = os.getcwd()
    CERT_FILE = os.path.join(current_working_dir, "cert.pem")
    KEY_FILE = os.path.join(current_working_dir, "key.pem")

    generate_self_signed_cert(CERT_FILE, KEY_FILE)
