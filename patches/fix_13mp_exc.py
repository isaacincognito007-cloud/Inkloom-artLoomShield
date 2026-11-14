from pathlib import Path

p = Path(r"D:\LoomShield\tests\e2e\test_ui_e2e.py")
text = p.read_text(encoding="utf-8")

old_str = """        from PIL import Image
        import io
        from backend.engine import inspect_raster_image
        img_13mp = Image.new("RGBA", (3700, 3600), (255, 255, 255, 255))
        buf = io.BytesIO()
        img_13mp.save(buf, format="PNG")
        try:
            inspect_raster_image(buf.getvalue(), [])
            cap_rejected = False
        except ValueError as exc:
            cap_rejected = True
            assert "12" in str(exc)"""

new_str = """        from PIL import Image
        import io
        from backend.engine import inspect_raster_image, ImageTooLargeError
        img_13mp = Image.new("RGBA", (3700, 3600), (255, 255, 255, 255))
        buf = io.BytesIO()
        img_13mp.save(buf, format="PNG")
        try:
            inspect_raster_image(buf.getvalue(), [])
            cap_rejected = False
        except (ImageTooLargeError, ValueError) as exc:
            cap_rejected = True
            assert "12" in str(exc)"""

assert old_str in text
text = text.replace(old_str, new_str, 1)

p.write_text(text, encoding="utf-8")
print("Updated 13 MP exception catch to ImageTooLargeError in test_ui_e2e.py")
