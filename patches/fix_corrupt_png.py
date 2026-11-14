from pathlib import Path

p = Path(r"D:\LoomShield\tests\e2e\test_ui_e2e.py")
text = p.read_text(encoding="utf-8")

old_corrupt = """        # 4. Edge Case: Corrupt PNG image
        corrupt_png_result = page.evaluate(\"\"\"async () => {
            const corruptBytes = new Uint8Array([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0xDE, 0xAD, 0xBE, 0xEF]);
            const fd = new FormData();
            fd.append('brand_id', 'novapay');
            fd.append('document_name', 'corrupt.png');
            fd.append('file', new Blob([corruptBytes], { type: 'image/png' }), 'corrupt.png');
            const res = await fetch('/api/audits/upload', { method: 'POST', body: fd });
            return { status: res.status, text: await res.text() };
        }\"\"\")
        assert corrupt_png_result["status"] == 400
        assert "image" in corrupt_png_result["text"].lower() or "decode" in corrupt_png_result["text"].lower() or "corrupt" in corrupt_png_result["text"].lower()"""

new_corrupt = """        # 4. Edge Case: Corrupt PNG image handled safely as Check Failed (Cycle 3 Scenario E)
        corrupt_png_result = page.evaluate(\"\"\"async () => {
            const corruptBytes = new Uint8Array([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0xDE, 0xAD, 0xBE, 0xEF]);
            const fd = new FormData();
            fd.append('brand_id', 'novapay');
            fd.append('document_name', 'corrupt.png');
            fd.append('file', new Blob([corruptBytes], { type: 'image/png' }), 'corrupt.png');
            const res = await fetch('/api/audits/upload', { method: 'POST', body: fd });
            return { status: res.status, data: await res.json() };
        }\"\"\")
        assert corrupt_png_result["status"] == 200
        assert corrupt_png_result["data"]["pillar_states"]["Brand Identity & Palette"] == "Check Failed"
        assert corrupt_png_result["data"]["pillar_states"]["Brand Identity & Palette"] != "Passed" """

assert old_corrupt in text, "old_corrupt not found"
text = text.replace(old_corrupt, new_corrupt, 1)

p.write_text(text, encoding="utf-8")
print("Updated corrupt PNG assertion in tests/e2e/test_ui_e2e.py")
