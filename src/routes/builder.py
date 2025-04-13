from quart import Blueprint, render_template, request, jsonify, send_file
import os
import tempfile
from util.builder.payload_builder import PayloadBuilder
from util.blacklist.ip_blacklist import black_list_ip

builder_bp = Blueprint("builder", __name__)


@builder_bp.route("/builder", methods=["GET"])
@black_list_ip()
async def builder_page():
    """Render the builder page"""
    return await render_template("builder/builder.html", active_page="builder")


@builder_bp.route("/api/build-payload", methods=["POST"])
@black_list_ip()
async def build_payload():
    """API endpoint to build a custom payload"""
    try:
        # Get the hostname:port from the request
        data = await request.get_json()
        hostname_port = data.get("hostname_port")

        if not hostname_port:
            return (
                jsonify({"status": "error", "message": "hostname_port is required"}),
                400,
            )

        builder = PayloadBuilder()

        payload = builder.build_custom_payload(hostname_port)

        return jsonify(
            {
                "status": "success",
                "payload": payload,
                "payload_base64": builder.get_payload_as_base64(hostname_port),
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@builder_bp.route("/api/download-payload", methods=["POST"])
@black_list_ip()
async def download_payload():
    """Download the generated payload file"""
    try:
        data = await request.get_json()
        hostname_port = data.get("hostname_port")

        if not hostname_port:
            return (
                jsonify({"status": "error", "message": "hostname_port is required"}),
                400,
            )

        builder = PayloadBuilder()

        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, f"out.ps1")

        builder.save_custom_payload(hostname_port, temp_file)

        return await send_file(
            temp_file,
            as_attachment=True,
            attachment_filename=f"out.ps1",
            mimetype="application/octet-stream",
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
