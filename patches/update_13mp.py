from pathlib import Path

p = Path(r"D:\LoomShield\tests\e2e\test_ui_e2e.py")
text = p.read_text(encoding="utf-8")

old_13mp = """        # 5. Edge Case: 13 Megapixels image rejection (exceeds 12 MP cap)
        from PIL import Image
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
            assert "12" in str(exc)
        assert cap_rejected, "Expected 13 MP image to be rejected by the 12 MP pixel cap" """

new_13mp = """        # 5. Edge Case: 13 Megapixels image rejection (exceeds 12 MP cap)
        from PIL import Image
        import io
        from backend.engine import inspect_raster_image
        img_13mp = Image.new("RGBA", (3700, 3600), (255, 255, 255, 255))
        buf = io.BytesIO()
        img_13mp.save(buf, format="PNG")
        res_13mp = inspect_raster_image(buf.getvalue(), [])
        assert res_13mp.get("too_large") is True
        assert res_13mp.get("inspect_ok") is False
        assert "12" in res_13mp.get("error", "")"""

assert old_13mp.strip() in text, "old_13mp not found"
text = text.replace(old_13mp.strip(), new_13mp.strip(), 1)

p.write_text(text, encoding="utf-8")
print("Updated 13 MP test in tests/e2e/test_ui_e2e.py")
