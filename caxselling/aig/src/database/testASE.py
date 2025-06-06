
from PIL import Image
import requests
import base64, io
import os
import json

def test_ase_add_ad():
    image_url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcStMP8S3VbNCqOQd7QQQcbvC_FLa1HlftCiJw&s"
    mydic={}

    im = Image.open(requests.get(image_url, stream=True).raw)
    buffered = io.BytesIO()
    im.save(buffered, format="JPEG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
    mydic['imgb64'] = img_b64
    mydic['description'] = "This is a test image of a llama with black background."
    mydic['id'] = 1
    mydic['source'] = "test_source"

    requests.post("http://localhost:5003/ase/predef/", json=mydic)

def test_ase_predef_query():
    res=requests.post("http://localhost:5003/ase/predef/query", json={"query": "banana", "n_results": 4})
    items=res.json()

    directory=os.path.expanduser("~")  # Uncomment to run the ad addition test
    
    for item in items:
        print(f"ID: {item['id']}, Description: {item['description']}, source: {item['source']}")
        img_bytes = base64.b64decode(item['imgb64'])
        image = Image.open(io.BytesIO(img_bytes))
        filename=f"test_{item['id']}.jpg"
        filepath = os.path.join(directory, filename)
        image.save(filepath)
        print(f"Image saved to {filepath}")

def test_ase_predef_query_with_adhoc():
    query_data = None
    with open("./caxselling/aig/src/database/samplequery.json", "r", encoding="utf-8") as f:
        query_data = json.load(f)

    res = requests.post("http://localhost:5003/ase/predef/query/ad", json=query_data)
    items = res.json()

    directory = os.path.expanduser("~")  # Uncomment to run the ad addition test
    
    res_counter=0
    for item in items:
        print(f"Result ID: {res_counter}")
        img_bytes = base64.b64decode(item['imgb64'])
        image = Image.open(io.BytesIO(img_bytes))
        filename = f"ad_with_addons_{res_counter}.jpg"
        filepath = os.path.join(directory, filename)
        image.save(filepath)
        res_counter += 1
        print(f"Image saved to {filepath}")

def get_unique_filenames(directory):
    files = os.listdir(directory)
    unique_files = set()
    for f in files:
        name, _ = os.path.splitext(f)
        unique_files.add(name)
    return unique_files

def test_load_sampledata():
    namedir = "~/CACS_SignageApproach/caxselling/aig/docker/sharedata/sample"
    directory = os.path.expanduser(namedir)
    filenames = get_unique_filenames(directory)

    for filename in filenames:
        filepath_jpg = os.path.join(directory, f"{filename}.jpg")
        
        im=Image.open(filepath_jpg)
        buffered = io.BytesIO()
        im.save(buffered, format="JPEG")
        img_bytes = buffered.getvalue()
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        mydic={}
        mydic['imgb64'] = img_b64
        mydic['source'] = "marketing"
        # To add, do not define the id because if it exists, it will be overwritten (update)

        filepath_txt = os.path.join(directory, f"{filename}.txt")
        with open(filepath_txt, 'r') as f:
            description = f.read().strip()
        
        mydic['description'] = description if description else "No description available."

        requests.post("http://localhost:5003/ase/predef/", json=mydic)
        print(f"Content: {filename}")

if __name__ == "__main__":
    #test_ase_add_ad()
    #test_ase_predef_query()  # Run the test function to check ASE predefined ads query functionality
    #test_load_sampledata()  # Run the test function to check loading sample data
    test_ase_predef_query_with_adhoc()
