from PIL import Image
import pytest

from imgproc.img_frame import ImgDecorator


class TestImgDecoratorValidation:
    """Test validation methods of ImgDecorator."""

    def test_is_color_valid_all_common_colors(self):
        """Test that common color names are recognized."""
        valid_colors = ["red", "blue", "green", "white", "black", "yellow", "cyan", "magenta"]
        for color in valid_colors:
            assert ImgDecorator.is_color_valid(color) is True

    def test_is_color_valid_case_insensitive(self):
        """Test color validation is case-insensitive."""
        assert ImgDecorator.is_color_valid("RED") is True
        assert ImgDecorator.is_color_valid("Blue") is True
        assert ImgDecorator.is_color_valid("gReEn") is True

    def test_is_color_valid_rejects_invalid(self):
        """Test that invalid colors are rejected."""
        invalid_colors = ["notacolor", "123color", "rgb(1,2,3)", ""]
        for color in invalid_colors:
            assert ImgDecorator.is_color_valid(color) is False

    def test_get_color_list_contains_expected_colors(self):
        """Test that get_color_list returns complete list of PIL colors."""
        colors = ImgDecorator.get_color_list()
        assert "red" in colors
        assert "blue" in colors
        assert "green" in colors
        assert "white" in colors
        assert "black" in colors
        assert len(colors) > 100


class TestFrameDrawing:
    """Test frame drawing functionality."""

    def test_draw_frame_double_border_creates_valid_image(self):
        """Test frame is drawn correctly."""
        img = Image.new("RGB", (200, 150), "white")
        out = ImgDecorator.draw_frame_double_border(img, percentageFromBorder=5)

        assert isinstance(out, Image.Image)
        assert out.size == (200, 150)
        assert out.mode == "RGB"

    def test_draw_frame_with_zero_percentage(self):
        """Test frame with minimum percentage."""
        img = Image.new("RGB", (100, 100), "white")
        out = ImgDecorator.draw_frame_double_border(img, percentageFromBorder=0)
        assert out.size == (100, 100)

    def test_draw_frame_with_max_percentage(self):
        """Test frame with maximum percentage."""
        img = Image.new("RGB", (100, 100), "white")
        out = ImgDecorator.draw_frame_double_border(img, percentageFromBorder=50)
        assert out.size == (100, 100)

    def test_draw_frame_converts_rgba_to_rgb(self):
        """Test frame handles RGBA images by converting to RGB."""
        img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        out = ImgDecorator.draw_frame_double_border(img)
        assert out.mode == "RGB"


class TestPriceDrawing:
    """Test price drawing functionality."""

    def test_count_digits_extracts_numeric_chars(self):
        """Test digit counting from various price formats."""
        assert ImgDecorator.count_digits("$9.99") == 3
        assert ImgDecorator.count_digits("100 dollars") == 3
        assert ImgDecorator.count_digits("$1,200.50") == 6
        assert ImgDecorator.count_digits("no numbers") == 0

    def test_count_digits_ignores_special_chars(self):
        """Test that special characters are ignored in counting."""
        assert ImgDecorator.count_digits("$$$123") == 3
        assert ImgDecorator.count_digits("---456---") == 3

    def test_count_points_commas_totals_separators(self):
        """Test counting of decimal points and commas."""
        assert ImgDecorator.count_points_commas("1,234.56") == 2
        assert ImgDecorator.count_points_commas("999.99") == 1
        assert ImgDecorator.count_points_commas("1,000,000.00") == 3
        assert ImgDecorator.count_points_commas("no separators") == 0


class TestLogoPlacement:
    """Test logo positioning and sizing."""

    def test_draw_logo_respects_size_percentage(self):
        """Test logo is scaled to requested percentage."""
        image = Image.new("RGB", (200, 200), "white")
        logo = Image.new("RGBA", (50, 50), (255, 0, 0, 255))

        out = ImgDecorator.draw_logo(image, logo, logo_percentage=20)
        assert out.size == (200, 200)

    def test_draw_logo_left_alignment(self):
        """Test logo left alignment."""
        image = Image.new("RGB", (200, 200), "white")
        logo = Image.new("RGBA", (50, 50), (255, 0, 0, 255))

        out = ImgDecorator.draw_logo(image, logo, align="left", valign="top")
        assert isinstance(out, Image.Image)

    def test_draw_logo_right_alignment(self):
        """Test logo right alignment."""
        image = Image.new("RGB", (200, 200), "white")
        logo = Image.new("RGBA", (50, 50), (255, 0, 0, 255))

        out = ImgDecorator.draw_logo(image, logo, align="right", valign="bottom")
        assert isinstance(out, Image.Image)

    def test_draw_logo_center_alignment(self):
        """Test logo center alignment."""
        image = Image.new("RGB", (200, 200), "white")
        logo = Image.new("RGBA", (50, 50), (255, 0, 0, 255))

        out = ImgDecorator.draw_logo(image, logo, align="center", valign="middle")
        assert isinstance(out, Image.Image)

    def test_draw_logo_converts_to_rgb(self):
        """Test logo handling of different image modes."""
        image = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        logo = Image.new("RGBA", (50, 50), (255, 0, 0, 255))

        out = ImgDecorator.draw_logo(image, logo)
        assert out.mode == "RGB"

    def test_draw_logo_validates_margin(self):
        """Test margin pixel parameter."""
        image = Image.new("RGB", (200, 200), "white")
        logo = Image.new("RGBA", (50, 50), (255, 0, 0, 255))

        out = ImgDecorator.draw_logo(image, logo, margin_px=20)
        assert out.size == (200, 200)


class TestInputValidation:
    """Test input validation across drawing functions."""

    def test_frame_rejects_non_image_input(self):
        """Test frame drawing rejects non-image objects."""
        with pytest.raises(TypeError):
            ImgDecorator.draw_frame_double_border("not an image")

    def test_logo_rejects_non_image_main(self):
        """Test logo drawing rejects non-image main input."""
        logo = Image.new("RGBA", (50, 50))
        with pytest.raises(TypeError):
            ImgDecorator.draw_logo("not an image", logo)

    def test_logo_rejects_non_image_logo(self):
        """Test logo drawing rejects non-image logo input."""
        image = Image.new("RGB", (200, 200))
        with pytest.raises(TypeError):
            ImgDecorator.draw_logo(image, "not an image")

    def test_frame_validates_percentage_bounds(self):
        """Test percentage must be in valid range."""
        image = Image.new("RGB", (100, 100))

        with pytest.raises(ValueError):
            ImgDecorator.draw_frame_double_border(image, percentageFromBorder=-0.1)

        with pytest.raises(ValueError):
            ImgDecorator.draw_frame_double_border(image, percentageFromBorder=100.1)

    def test_logo_validates_percentage_bounds(self):
        """Test logo percentage must be in valid range."""
        image = Image.new("RGB", (200, 200))
        logo = Image.new("RGBA", (50, 50))

        with pytest.raises(ValueError):
            ImgDecorator.draw_logo(image, logo, logo_percentage=-1)

        with pytest.raises(ValueError):
            ImgDecorator.draw_logo(image, logo, logo_percentage=101)

    def test_alignment_values_validated(self):
        """Test that invalid alignment values are rejected."""
        image = Image.new("RGB", (100, 100))
        logo = Image.new("RGBA", (50, 50))

        with pytest.raises(ValueError):
            ImgDecorator.draw_logo(image, logo, align="invalid")

        with pytest.raises(ValueError):
            ImgDecorator.draw_logo(image, logo, valign="invalid")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_digit_count_with_none(self):
        """Test digit counting with None input."""
        assert ImgDecorator.count_digits(None) == 0

    def test_digit_count_with_non_string(self):
        """Test digit counting with non-string input."""
        assert ImgDecorator.count_digits(123) == 0

    def test_points_commas_with_none(self):
        """Test separator counting with None input."""
        assert ImgDecorator.count_points_commas(None) == 0

    def test_points_commas_with_non_string(self):
        """Test separator counting with non-string input."""
        assert ImgDecorator.count_points_commas([1, 2]) == 0

    def test_color_valid_with_various_invalid_inputs(self):
        """Test color validation with various invalid types."""
        assert ImgDecorator.is_color_valid(None) is False
        assert ImgDecorator.is_color_valid(123) is False
        assert ImgDecorator.is_color_valid([]) is False
        assert ImgDecorator.is_color_valid({}) is False


class TestLargeImages:
    """Test with larger images."""

    def test_frame_with_large_image(self):
        """Test frame drawing on large image."""
        large_img = Image.new("RGB", (2000, 1500), "white")
        out = ImgDecorator.draw_frame_double_border(large_img, percentageFromBorder=3)
        assert out.size == (2000, 1500)

    def test_logo_with_large_image(self):
        """Test logo placement on large image."""
        large_img = Image.new("RGB", (2000, 1500), "white")
        logo = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
        out = ImgDecorator.draw_logo(large_img, logo, logo_percentage=15)
        assert out.size == (2000, 1500)

    def test_frame_with_small_image(self):
        """Test frame drawing on small image."""
        small_img = Image.new("RGB", (50, 50), "white")
        out = ImgDecorator.draw_frame_double_border(small_img, percentageFromBorder=5)
        assert out.size == (50, 50)


class TestColorValidation:
    """Test comprehensive color validation."""

    def test_all_basic_colors(self):
        """Test all basic color names are recognized."""
        basic_colors = [
            "maroon", "red", "orange", "yellow", "olive", "green",
            "cyan", "blue", "navy", "purple", "magenta", "gray",
            "silver", "white", "black"
        ]
        for color in basic_colors:
            assert ImgDecorator.is_color_valid(color) is True

    def test_get_color_list_exhaustive(self):
        """Test that color list is exhaustive."""
        colors = ImgDecorator.get_color_list()
        assert len(colors) >= 140
        assert isinstance(colors, list)
