import os
import io
import base64
from PIL import Image
# Logging
import logging
logger = logging.getLogger(__name__)

class SharedUtils:

    categories={
        'bread': 275859,
        'meat_beef': 959298,
        'water': 956546,
        'vegetables': 739033,
        'dairy': 312744,
        'oranges': 431937,
        'meat_pork': 363743,
        'meat_chicken': 937709,
        'meat_turkey': 229699,
        'fruits': 907387,
        'meat_lamb': 991967
    }

    @staticmethod
    def get_unique_filenames(directory):
        files = os.listdir(directory)
        unique_files = set()
        for f in files:
            name, _ = os.path.splitext(f)
            unique_files.add(name)
        return unique_files

    @staticmethod
    def load_sampledata(collection,namedir):
        if collection is None or namedir is None:
            return None
        
        if not os.path.exists(namedir):
            logger.error(f"[SharedUtils] Directory {namedir} does not exist.")
            return None
        
        directory = os.path.expanduser(namedir)
        filenames = SharedUtils.get_unique_filenames(directory)
        rdos=[]
        for filename in filenames:
            mydic={}
            try:
                # Image processing
                filepath_jpg = os.path.join(directory, f"{filename}.jpg")            
                im=Image.open(filepath_jpg)
                mydic['image'] = im
                
                #Source and ID
                myID = SharedUtils.categories.get(filename, -1)  # Use the filename as the id if it exists in categories, else -1
                if myID == -1:
                    print(f"Warning: Category '{filename}' not found in predefined categories. Using -1 as id.")
                    continue  # Skip this file if the category is not found
                else:
                    mydic['id'] = myID
                    mydic['source'] = "marketing"
                
                # Description processing
                filepath_txt = os.path.join(directory, f"{filename}.txt")
                with open(filepath_txt, 'r') as f:
                    description = f.read().strip()            
                mydic['description'] = description if description else "No description available."
                
                rdos.append(mydic)
            except Exception as e:
                logger.error(f"[SharedUtils] Error processing file {filename}: {e}")
                continue
        
        return rdos

