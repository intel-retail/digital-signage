import os
import textwrap
import math
from PIL import Image,ImageDraw, ImageFont, ImageColor
from database.version import AigServerMetadata

class ImgDecorator:    
    def is_color_valid(color: str) -> bool:
        """
        Checks if the given color string is a valid color name in PIL.
        """
        if color is None or not isinstance(color, str):
            return False
        
        return color.lower() in ImageColor.colormap
    
    def get_color_list():
        return list(ImageColor.colormap.keys())  # Returns a list of all available color names in PIL

    def draw_frame_double_border(img,percentageFromBorder:float=2):
        """
        Draws a double border frame around the image.
        """
        if not isinstance(img, Image.Image):
            raise TypeError(f"Input must be a PIL Image object. Received {type(img)}")            
        
        if percentageFromBorder < 0 or percentageFromBorder > 100:
            raise ValueError("percentageFromBorder must be between 0 and 100")
                
        if img.mode != 'RGB':
            img = img.convert('RGB') #RGBA is alpha channel for transparency

        x,y = img.size        
        draw = ImageDraw.Draw(img)

        #Frame 1
        xsep = x * percentageFromBorder / 100
        ysep = y * percentageFromBorder / 100
        xleft, xright = xsep, x-xsep
        yhigh, ylow = ysep, y-ysep
        frame1_line_width=1
        frame1_line_color='gray'

        draw.line((xleft, yhigh, xright, yhigh), fill=frame1_line_color, width=frame1_line_width)
        draw.line((xleft, ylow, xright, ylow), fill=frame1_line_color, width=frame1_line_width)
        draw.line((xleft, yhigh, xleft, ylow), fill=frame1_line_color, width=frame1_line_width)
        draw.line((xright, yhigh, xright, ylow), fill=frame1_line_color, width=frame1_line_width)

        #Frame 2
        xleft, xright = xsep/2, x-(xsep/2)
        yhigh, ylow = ysep/2, y-(ysep/2)
        frame2_line_width=3
        frame2_line_color='white'

        draw.line((xleft, yhigh, xright, yhigh), fill=frame2_line_color, width=frame2_line_width)
        draw.line((xleft, ylow, xright, ylow), fill=frame2_line_color, width=frame2_line_width)
        draw.line((xleft, yhigh, xleft, ylow), fill=frame2_line_color, width=frame2_line_width)
        draw.line((xright, yhigh, xright, ylow), fill=frame2_line_color, width=frame2_line_width)        

        return img
    
    def draw_price_raw(img, price: str, 
                       align: str = "center", # horizontal: "left", "center", "right"
                       valign:str = "bottom", # vertical: "top", "middle", "bottom"
                       margin_percentage: float = 2, #Percentage of margin (accoording to figure size) when the text falls into the border
                       font_size: int = 20, 
                       line_width: int = 20,
                       price_color: str = 'black'):
        """
        Draws a price string on the image with specified alignment and margins.
        """

        if not isinstance(img, Image.Image):
            raise TypeError(f"Input must be a PIL Image object. Received {type(img)}")
        
        if not isinstance(align,str) or align not in ["left", "center", "right"]:
            raise ValueError("align must be 'left', 'center', or 'right'")
        
        if not isinstance(valign,str) or valign not in ["top", "middle", "bottom"]:
            raise ValueError("valign must be 'top', 'middle', or 'bottom'")
        
        if img.mode != 'RGB':
            img = img.convert('RGB')

        font = None
        try:
            font = ImageFont.truetype(AigServerMetadata.get_font_path(), font_size)
        except Exception:
            font = ImageFont.load_default()

        draw = ImageDraw.Draw(img)
        lines = textwrap.wrap(price, width=line_width)

        # Calculate total text block height and max width
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])
        text_block_height = sum(line_heights)
        text_block_width = max(line_widths)

        img_width, img_height = img.size
        x_margin = img_width * margin_percentage / 100
        y_margin = img_height * margin_percentage / 100

        # Horizontal alignment
        if align == "center":
            x = (img_width - text_block_width) // 2 
        elif align == "right":
            x = img_width - text_block_width - x_margin
        else:  # "left" or default
            x = x_margin

        # Vertical alignment
        if valign in ("middle", "center"):
            y = (img_height - text_block_height) // 2
        elif valign == "bottom":
            y = img_height - text_block_height - y_margin
        else:  # "top" or default
            y = y_margin

        # Draw each line
        for i, line in enumerate(lines):
            line_width = line_widths[i]
            line_height = line_heights[i]
            # Adjust x for each line if horizontal align is center or right
            if align == "center":
                line_x = x + (text_block_width - line_width) // 2
            elif align == "right":
                line_x = x + (text_block_width - line_width)
            else:  # left
                line_x = x
            draw.text((line_x, y), line, font=font, fill=price_color, align="center", direction="ltr")
            y += line_height

        return img

    def count_digits(price: str) -> int:
        """Count the number of digits in a price string."""
        if price is None:
            return 0
        if not isinstance(price, str):
            return 0
        
        return sum(c.isdigit() for c in price if c not in ['$', ' ', '/'])

    def count_points_commas(price: str) -> int:
        """Count the number of digits in a price string."""
        if price is None:
            return 0
        if not isinstance(price, str):
            return 0
        
        points = price.count('.')
        commas = price.count(',')
        
        return points + commas
    
    def draw_price_circle(img, price: str, 
                          price_color: str = 'white', # color of the text
                       circle_color: str = 'black', # color of the circle behind the text
                       align: str = "center", # horizontal: "left", "center", "right"
                       valign:str = "bottom", # vertical: "top", "middle", "bottom"
                       margin_percentage: float = 2, #Percentage of margin (accoording to figure size) when the text falls into the border
                       font_size: int = 20, 
                       line_width: int = 20):
        """
        Draws a price string on the image with a circle behind it, specified alignment, and margins.
        """
        if not isinstance(img, Image.Image):
            raise TypeError(f"Input must be a PIL Image object. Received {type(img)}")
        
        if not isinstance(align,str) or align not in ["left", "center", "right"]:
            raise ValueError("align must be 'left', 'center', or 'right'")
        
        if not isinstance(valign,str) or valign not in ["top", "middle", "bottom"]:
            raise ValueError("valign must be 'top', 'middle', or 'bottom'")
        
        nnumbers = ImgDecorator.count_digits(price)
        npoints = ImgDecorator.count_points_commas(price)
        if line_width < (nnumbers + npoints):
            line_width = nnumbers + npoints 

        if img.mode != 'RGB':
            img = img.convert('RGB')

        font = None
        try:
            font = ImageFont.truetype(AigServerMetadata.get_font_path(), font_size)
        except Exception:
            font = ImageFont.load_default()

        draw = ImageDraw.Draw(img)
        lines = textwrap.wrap(price, width=line_width)

        # Calculate total text block height and max width
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])
        text_block_height = sum(line_heights)
        text_block_width = max(line_widths)

        img_width, img_height = img.size
        x_margin = img_width * margin_percentage / 100
        y_margin = img_height * margin_percentage / 100

        # Horizontal alignment
        if align == "center":
            x = (img_width - text_block_width) // 2 
        elif align == "right":
            x = img_width - text_block_width - x_margin
        else:  # "left" or default
            x = x_margin

        # Vertical alignment
        if valign in ("middle", "center"):
            y = (img_height - text_block_height) // 2
        elif valign == "bottom":
            y = img_height - text_block_height - y_margin
        else:  # "top" or default
            y = y_margin

        # --- Draw black circle behind text block ---
        # Find center of the text block
        center_x = x + text_block_width // 2
        center_y = y + text_block_height // 2
        # Circle radius: half the diagonal of the text block, plus padding
        circle_padding = 10  # Padding around the circle
        radius = int(math.sqrt(text_block_width**2 + text_block_height**2) / 2) + circle_padding
        # Bounding box for the circle
        left_up = (center_x - radius, center_y - radius)
        right_down = (center_x + radius, center_y + radius)
        draw.ellipse([left_up, right_down], fill=circle_color)

        # Draw each line
        for i, line in enumerate(lines):
            line_width = line_widths[i]
            line_height = line_heights[i]
            # Adjust x for each line if horizontal align is center or right
            #Center aligned price
            line_x = x + (text_block_width - line_width) // 2
            # line_x = x + (text_block_width - line_width) #Right aligned
            # line_x = x #Left aligned
            draw.text((line_x, y), line, font=font, fill=price_color, align="center", direction="ltr")
            y += line_height

        return img
              
    def draw_promo_rounded_rect(
        img, text: str,
        text_color: str = 'white',
        rect_color: str = 'black',
        align: str = "center",
        valign: str = "bottom",
        margin_percentage: float = 2,
        font_size: int = 20,
        line_width: int = 20,
        rect_padding: int = 10,      # Padding around the text block
        rect_radius: int = 20        # Corner radius for rounded rectangle
    ):
        if not isinstance(img, Image.Image):
            raise TypeError(f"Input must be a PIL Image object. Received {type(img)}")
        if not isinstance(align, str) or align not in ["left", "center", "right"]:
            raise ValueError("align must be 'left', 'center', or 'right'")
        if not isinstance(valign, str) or valign not in ["top", "middle", "bottom"]:
            raise ValueError("valign must be 'top', 'middle', or 'bottom'")

        if img.mode != 'RGB':
            img = img.convert('RGB')

        try:
            font = ImageFont.truetype(AigServerMetadata.get_font_path(), font_size)
        except Exception:
            font = ImageFont.load_default()

        draw = ImageDraw.Draw(img)
        lines = textwrap.wrap(text, width=line_width)

        # Calculate total text block height and max width
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])
        text_block_height = sum(line_heights)
        text_block_width = max(line_widths)

        img_width, img_height = img.size
        x_margin = img_width * margin_percentage / 100
        y_margin = img_height * margin_percentage / 100

        # Horizontal alignment
        if align == "center":
            x = (img_width - text_block_width) // 2
        elif align == "right":
            x = img_width - text_block_width - x_margin
        else:  # "left" or default
            x = x_margin

        # Vertical alignment
        if valign in ("middle", "center"):
            y = (img_height - text_block_height) // 2
        elif valign == "bottom":
            y = img_height - text_block_height - y_margin
        else:  # "top" or default
            y = y_margin

        # --- Draw rounded rectangle behind text block ---
        rect_left = x - rect_padding
        rect_top = y - rect_padding
        rect_right = x + text_block_width + rect_padding
        rect_bottom = y + text_block_height + rect_padding
        draw.rounded_rectangle(
            [rect_left, rect_top, rect_right, rect_bottom],
            radius=rect_radius,
            fill=rect_color
        )

        # Draw each line
        y_line = y
        for i, line in enumerate(lines):
            line_width = line_widths[i]
            line_height = line_heights[i]
            # Centered text
            line_x = x + (text_block_width - line_width) // 2
            # line_x = x + (text_block_width - line_width) #Right aligned
            # line_x = x # Left aligned
            draw.text((line_x, y_line), line, font=font, fill=text_color, align="center", direction="ltr")
            y_line += line_height

        return img    

    def draw_logo(img, logo_img, 
                       align: str = "left", # horizontal: "left", "center", "right"
                       valign:str = "top", # vertical: "top", "middle", "bottom"
                       logo_percentage: float = 25,
                       margin_px: int = 10):
        """
        Draws a logo on the image with specified alignment and margins.
        """
        if not isinstance(img, Image.Image):
            raise TypeError(f"Input must be a PIL Image object. Received {type(img)}")
        if not isinstance(logo_img, Image.Image):
            raise TypeError("logo_img must be a PIL Image object")
        if not isinstance(align, str) or align not in ["left", "center", "right"]:
            raise ValueError("align must be 'left', 'center', or 'right'")
        if not isinstance(valign, str) or valign not in ["top", "middle", "bottom"]:
            raise ValueError("valign must be 'top', 'middle', or 'bottom'")
        if logo_percentage < 0 or logo_percentage > 100:
            raise ValueError("logo_percentage must be between 0 and 100")
        
        img_rgba = img.convert('RGBA')
        logo_rgba = logo_img.convert('RGBA')

        # Optionally resize the logo
        main_width, main_height = img_rgba.size
        logo_size = (int(main_width* (logo_percentage / 100.0)), 
                     int(main_height * (logo_percentage / 100.0)))
        logo_rgba = logo_rgba.resize(logo_size, Image.LANCZOS)

        # Choose position 
        logo_width, logo_height = logo_rgba.size
        x_position = None
        if align == "center":
            x_position = main_width // 2 - logo_width // 2
        elif align == "left":
            x_position = margin_px
        elif align == "right":
            x_position = main_width - logo_width - margin_px

        y_position = None
        if valign == "middle":
            y_position = main_height // 2 - logo_height // 2
        elif valign == "top":
            y_position = margin_px
        elif valign == "bottom":
            y_position = main_height - logo_height - margin_px
        
        position = (x_position, y_position)

        # Paste the logo using itself as mask for transparency
        img_rgba.paste(logo_rgba, position, mask=logo_rgba)
        img_rgb = img_rgba.convert('RGB')  # Convert back to RGB if needed
        
        return img_rgb

    def draw_slogan(
        img, text: str,
        text_color: str = 'white',
        align: str = "center",
        valign: str = "bottom",
        margin_percentage: float = 2,
        font_size: int = 20,
        line_width: int = 20
    ):
        """
        Draws a slogan text on the image with specified alignment and margins.
        """
        if not isinstance(img, Image.Image):
            raise TypeError(f"Input must be a PIL Image object. Received {type(img)}")
        if not isinstance(align, str) or align not in ["left", "center", "right"]:
            raise ValueError("align must be 'left', 'center', or 'right'")
        if not isinstance(valign, str) or valign not in ["top", "middle", "bottom"]:
            raise ValueError("valign must be 'top', 'middle', or 'bottom'")

        if img.mode != 'RGB':
            img = img.convert('RGB')

        try:
            font = ImageFont.truetype(AigServerMetadata.get_font_path(), font_size)
        except Exception:
            font = ImageFont.load_default()

        draw = ImageDraw.Draw(img)
        lines = textwrap.wrap(text, width=line_width)

        # Calculate total text block height and max width
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])
        text_block_height = sum(line_heights)
        text_block_width = max(line_widths)

        img_width, img_height = img.size
        x_margin = img_width * margin_percentage / 100
        y_margin = img_height * margin_percentage / 100

        # Horizontal alignment
        if align == "center":
            x = (img_width - text_block_width) // 2
        elif align == "right":
            x = img_width - text_block_width - x_margin
        else:  # "left" or default
            x = x_margin

        # Vertical alignment
        if valign in ("middle", "center"):
            y = (img_height - text_block_height) // 2
        elif valign == "bottom":
            y = img_height - text_block_height - y_margin
        else:  # "top" or default
            y = y_margin

        # Draw each line
        y_line = y
        for i, line in enumerate(lines):
            line_width = line_widths[i]
            line_height = line_heights[i]
            # Centered text
            line_x = x + (text_block_width - line_width) // 2
            # line_x = x + (text_block_width - line_width) #Right aligned
            # line_x = x # Left aligned
            draw.text((line_x, y_line), line, font=font, fill=text_color, align="center", direction="ltr")
            y_line += line_height

        return img    


#if __name__ == "__main__":
#    import sys
#    from PIL import Image

    #print(', '.join(ImgDecorator.get_color_list()))  # Print available colors in PIL
    
    #print(ImgDecorator.is_color_valid(""))  # Print available colors in PIL
    #print(ImgDecorator.is_color_valid("rojo"))  # Print available colors in PIL
    #print(ImgDecorator.is_color_valid("RED"))  # Print available colors in PIL
    #print(ImgDecorator.is_color_valid("bLack"))  # Print available colors in PIL
    # Example usage
    #print(os.getcwd())  # Change to the directory where the script is located
    #img = Image.open("./caxselling/aig/src/imgproc/test.jpg")  # Load an image from file
    #logo = Image.open("./caxselling/aig/src/imgproc/sample_logo.png")  # Load a logo image from file
    #img_with_frame = ImgDecorator.draw_frame_double_border(img,2)
    #img_with_frame.show()  # Display the image with the frame
    #img2 = ImgDecorator.draw_price_circle(img, "5.54 $/lb", align="right", valign="bottom", font_size=24, line_width=5, margin_percentage=10, circle_color="blue")    
    #img3 = ImgDecorator.draw_promo_rounded_rect(img2, "Buy 1, Get 50% in 2nd unit", align="left", valign="bottom", font_size=20, line_width=10, margin_percentage=10, rect_color="blue", rect_padding=10, rect_radius=20)
    #img4 = ImgDecorator.draw_frame_double_border(img3, 2)  # Add frame to the image with text
    #img5 = ImgDecorator.draw_logo(img4, logo, align="left", valign="top", logo_percentage=15, margin_px=10)  # Add logo to the image with text and frame
    #img6 = ImgDecorator.draw_slogan(img5, "Best Price in Town!", align="right", valign="top", font_size=18, line_width=20, margin_percentage=5)  # Add slogan to the image with logo and frame
    
    #img6.save("./caxselling/aig/src/imgproc/output_image_from_file.jpg")  # Save the image with the frame