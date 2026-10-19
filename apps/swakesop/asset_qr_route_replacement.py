## version 1
from mini_qr_client import MiniQrRenderError, render_mini_qr_png


@app.route("/a/<asset_key>/qr.png")
def asset_qr(asset_key):
    asset = Asset.query.filter_by(asset_key=asset_key).first_or_404()
    qr_target = asset_public_url(asset)

    try:
        buffer = io.BytesIO(render_mini_qr_png(qr_target))
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype="image/png",
            download_name=f"{asset.asset_key}.png",
        )
    except MiniQrRenderError as exc:
        app.logger.exception("Mini QR render failed for %s: %s", asset.asset_key, exc)

        fallback_image = qrcode.make(qr_target)
        fallback_buffer = io.BytesIO()
        fallback_image.save(fallback_buffer, format="PNG")
        fallback_buffer.seek(0)
        return send_file(
            fallback_buffer,
            mimetype="image/png",
            download_name=f"{asset.asset_key}.png",
        )
