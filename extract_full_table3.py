import fitz

pdf_path = "d:/DocRag/demo_dataset/Artificial_Intelligence/Attention Is All You Need.pdf"
doc = fitz.open(pdf_path)

# Get page 9 (0-indexed page 8)
page = doc[8]
text = page.get_text()

# Find Table 3 and extract its content
lines = text.split('\n')
for i, line in enumerate(lines):
    if 'Table 3: Variations on the Transformer architecture' in line:
        # Extract the table content (about 20 lines)
        start = i
        end = min(len(lines), i + 25)
        table_content = '\n'.join(lines[start:end])
        print(table_content)
        break
