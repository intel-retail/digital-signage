import chromadb
chroma_client = chromadb.HttpClient(host="localhost", port=8000)

collection_name="ase-collection"
if chroma_client is not None:
    collection = chroma_client.get_or_create_collection(name=collection_name)

    if collection is not None:
        print(f"[ChromaDB] Collection '{collection_name}' created successfully.")
    else:
        print(f"[ChromaDB] Failed to create collection '{collection_name}'.")
else:
    print("[ChromaDB] Failed to initialize Chroma client.")
    collection = None

def test_add_chromadb():   
    #Test the ChromaDB connection by inserting a dummy document.
    
    if collection is not None:
        try:
            collection.add(
                documents=["This is a test defining citrics and their variety."],
                metadatas=[{"source": "test"}],
                ids=["test_doc_1"]
            )
            collection.add(
                documents=["This is another test document describing apples and bananas."],
                metadatas=[{"source": "test2"}],
                ids=["test_doc_2"]
            )                

            results=collection.query(
                query_texts=["What is the document most related to oranges?"],
                n_results=2
            )  # Query the collection

            print(f"[ChromaDB] Query results: {results}")
            print("[ChromaDB] Test document added successfully.")
        except Exception as e:
            print(f"[ChromaDB] Error adding test document: {e}")
    else:
        print("[ChromaDB] Collection is not initialized.")

def test_query_chromadb():
    #Test the ChromaDB query functionality.
    
    if collection is not None:
        try:
            results = collection.query(
                #query_texts=["What is the document most related to oranges?"],
                query_texts=["content related to dairy?"],
                n_results=3
            )  # Query the collection

            print(f"[ChromaDB] Query results: {results}")

            if 'included' in results:
                if 'metadatas' in results['included']:
                    print(f"[OK] metadatas")
                else:
                    print(f"[ERROR] metadatas not found in results['included']")
            else:
                print(f"[ERROR] 'included' not found in results")

            if 'ids' not in results or 'metadatas' not in results:
                print(f"[ERROR] 'ids' or 'metadatas' not found in results")
                return
            
            ids = results.get('ids',[])
            metadatas = results.get('metadatas',[])
            distances = results.get('distances',[])

            for query_index, (id_list, metadata_list,distance_list) in enumerate (zip(ids, metadatas, distances)):
                for doc_index, doc_id in enumerate(id_list):
                    try:
                        doc_metadata = metadata_list[doc_index]                        
                        doc_distance = distance_list[doc_index]

                        if doc_distance is not None and doc_distance < 0.75:
                            id_int = int(doc_id)
                            description = doc_metadata.get('description',None)
                            img_path = doc_metadata.get('img_path',None)

                            print(f"[ChromaDB] Document ID: {id_int}, Description: {description}, Image Path: {img_path}")
                        else:
                            print(f"[ChromaDB] Document ID: {doc_id}, discarded by distance: {doc_distance}")
                    except Exception as e:
                        print(f"[ChromaDB] ID is not integer {doc_id}: {e}")

        except Exception as e:
            print(f"[ChromaDB] Error querying collection: {e}")
    else:
        print("[ChromaDB] Collection is not initialized.")

def test_query_chromadb_get(id):
    #Test the ChromaDB query functionality.
    
    if collection is not None:
        try:
            results = collection.get(ids=[id])  # Get the document by ID
            

            print(f"[ChromaDB] Query results: {results}")

            if 'included' in results:
                if 'metadatas' in results['included']:
                    print(f"[OK] metadatas")
                else:
                    print(f"[ERROR] metadatas not found in results['included']")
            else:
                print(f"[ERROR] 'included' not found in results")

            if 'ids' not in results or 'metadatas' not in results:
                print(f"[ERROR] 'ids' or 'metadatas' not found in results")
                return
            
            ids = results.get('ids',[])
            metadatas = results.get('metadatas',[])

            for query_index, (id_list, metadata_list) in enumerate (zip(ids, metadatas)):
                for doc_index, doc_id in enumerate(id_list):
                    try:
                        print(f"[ChromaDB] Document ID: {metadata_list}")
                        doc_metadata = metadata_list
                        
                        id_int = int(doc_id)
                        description = doc_metadata.get('description',None)
                        img_path = doc_metadata.get('img_path',None)

                        print(f"[ChromaDB] Document ID: {id_int}, Description: {description}, Image Path: {img_path}")                    
                    except Exception as e:
                        print(f"[ChromaDB] ID is not integer {doc_id}: {e}")

        except Exception as e:
            print(f"[ChromaDB] Error querying collection: {e}")
    else:
        print("[ChromaDB] Collection is not initialized.")

if  __name__ == "__main__":
    print(f"Collection #{collection_name} initialized. Elements: {collection.count()}")

    test_query_chromadb()
