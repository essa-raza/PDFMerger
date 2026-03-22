from PIL import Image

img = Image.open("pdf.png")

img.save("pdf_merger.ico", format="ICO", sizes=[
    (16,16),
    (32,32),
    (48,48),
    (64,64),
    (128,128),
    (256,256)
])

print("Icon created: pdf_merger.ico")
