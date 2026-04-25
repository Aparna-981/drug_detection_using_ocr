import re

def _smart_correct_batch(t: str) -> str:
    if not t: return ""
    t = t.strip().upper()
    digit_count = sum(c.isdigit() for c in t)
    total_len   = len(t)
    if digit_count >= total_len / 2:
        t = t.replace('Z', '2').replace('S', '5')
    t = re.sub(r'(?<=\d)O(?=\d)', '0', t)
    t = re.sub(r'(?<=\d)O$', '0', t)
    t = re.sub(r'^O(?=\d)', '0', t)
    t = re.sub(r'(?<=\d)I(?=\d)', '1', t)
    t = re.sub(r'(?<=\d)I$', '1', t)
    t = re.sub(r'^I(?=\d)', '1', t)
    return t

def _smart_correct_date(t: str) -> str:
    if not t: return ""
    t = t.strip().upper()
    parts = re.split(r'([\s/\-.\\]+)', t)
    new_parts = []
    for p in parts:
        if re.search(r'[A-Z]{3,}', p) and any(m in p.lower() for m in ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']):
            new_parts.append(p)
            continue
        if re.search(r'[\dIOZSL]', p):
            p = p.replace('O', '0').replace('I', '1').replace('L', '1').replace('Z', '2').replace('S', '5')
        new_parts.append(p)
    return "".join(new_parts)

def _conservative_correct_text(text: str) -> str:
    if not text: return ""
    text = re.sub(r'([A-Z])5([A-Z]?)', r'\1S\2', text)
    text = re.sub(r'^5([A-Z])', r'S\1', text)
    text = re.sub(r'([A-Z])0([A-Z]?)', r'\1O\2', text)
    text = re.sub(r'^0([A-Z])', r'O\1', text)
    text = re.sub(r'([A-Z])1([A-Z])', r'\1I\2', text)
    text = re.sub(r'\b5YRUP\b', 'SYRUP', text, flags=re.I)
    text = re.sub(r'\bTAB1ETS\b', 'TABLETS', text, flags=re.I)
    text = re.sub(r'\bCAP5ULE5\b', 'CAPSULES', text, flags=re.I)
    return text.strip()

print("--- TEXT CORRECTION ---")
print(f"'5YRUP' -> '{_conservative_correct_text('5YRUP')}'")
print(f"'DOLO 650' -> '{_conservative_correct_text('DOLO 650')}'")
print(f"'PANT0P' -> '{_conservative_correct_text('PANT0P')}'")
print(f"'650' -> '{_conservative_correct_text('650')}'")

print("\n--- BATCH CORRECTION ---")
print(f"'SP24O16S' -> '{_smart_correct_batch('SP24O16S')}'")
print(f"'AXI23003P' -> '{_smart_correct_batch('AXI23003P')}'")

print("\n--- DATE CORRECTION ---")
print(f"'MAY ZOZ5' -> '{_smart_correct_date('MAY ZOZ5')}'")
print(f"'10/ZOZ6' -> '{_smart_correct_date('10/ZOZ6')}'")
