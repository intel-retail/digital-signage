from PIL import Image, ImageDraw, ImageFont

# Image size and background (RGBA for transparency)
width, height = 256, 256
img = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # Fully transparent

draw = ImageDraw.Draw(img)

# Draw a semi-transparent colored circle
circle_color = (30, 144, 255, 180)  # DodgerBlue with alpha
circle_radius = 100
center = (width // 2, height // 2)
draw.ellipse(
    [
        (center[0] - circle_radius, center[1] - circle_radius),
        (center[0] + circle_radius, center[1] + circle_radius)
    ],
    fill=circle_color
)

# Draw centered text (white)
try:
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 48)
except Exception:
    font = ImageFont.load_default()

text = "LOGO"
bbox = draw.textbbox((0, 0), text, font=font)
text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]
text_x = (width - text_width) // 2
text_y = (height - text_height) // 2

draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))

# Save as PNG with transparency
img.save("./caxselling/aig/src/imgproc/sample_logo.png", "PNG")
print("Sample logo saved as sample_logo.png")
