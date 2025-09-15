from components.Editor.ImageEditor.ImageEditor import ImageEditor


def test_image_editor():
    imageEditor = ImageEditor()
    img = imageEditor.load_picture("volume/resources/images/rick/rick_explaining_with_both_hands.png")
    w,h = imageEditor.get_size(img)
    print(f"Width - Height: {w} - {h}")
    img2 = imageEditor.resize_keep_aspect(img, target_w=720)
    img3 = imageEditor.cut_borders(img2, left=50, top=35)
    img_path = imageEditor.save_image(img3, "volume/output/imageeditor/test01/output.png")
    print("Saved succcesfully on:", img_path)
