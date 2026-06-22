from PIL import Image
import pytest

from imgproc.img_frame import ImgDecorator


def test_is_color_valid_handles_valid_and_invalid_values():
    assert ImgDecorator.is_color_valid("red") is True
    assert ImgDecorator.is_color_valid("not-a-color") is False
    assert ImgDecorator.is_color_valid(None) is False


def test_count_digits_and_points_commas():
    assert ImgDecorator.count_digits("$12.50 / lb") == 4
    assert ImgDecorator.count_points_commas("1,200.50") == 2
    assert ImgDecorator.count_digits(None) == 0


def test_draw_frame_double_border_validates_input_type():
    with pytest.raises(TypeError):
        ImgDecorator.draw_frame_double_border("not-an-image")


def test_draw_frame_double_border_returns_image():
    image = Image.new("RGB", (100, 80), "white")
    framed = ImgDecorator.draw_frame_double_border(image, percentageFromBorder=2)

    assert isinstance(framed, Image.Image)
    assert framed.size == (100, 80)


def test_draw_logo_validates_percentage_range():
    image = Image.new("RGB", (100, 80), "white")
    logo = Image.new("RGBA", (10, 10), (255, 0, 0, 255))

    with pytest.raises(ValueError):
        ImgDecorator.draw_logo(image, logo, logo_percentage=120)


def test_draw_logo_returns_image_with_expected_size():
    image = Image.new("RGB", (120, 90), "white")
    logo = Image.new("RGBA", (20, 20), (0, 0, 255, 180))

    out = ImgDecorator.draw_logo(image, logo, align="left", valign="top", logo_percentage=25)

    assert isinstance(out, Image.Image)
    assert out.size == image.size
