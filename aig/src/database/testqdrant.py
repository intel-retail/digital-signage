import os
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

HOST = os.getenv("ASE_QDRANT_HOST", "localhost")
PORT = int(os.getenv("ASE_QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("ASE_COLLECTION_NAME", "ase-collection")
MODEL_PATH = os.getenv("ASE_MODEL_PATH", "/opt/models/all-MiniLM-L12-v2")


def get_similarity_threshold() -> float:
    explicit_score = os.getenv("ASE_QDRANT_SCORE_MIN_THRESHOLD")
    if explicit_score is not None:
        return float(explicit_score)

    legacy_distance = float(os.getenv("ASE_DISTANCE_MAX_THRESHOLD", 0.2))
    return 1.0 - legacy_distance


SIMILARITY_THRESHOLD = get_similarity_threshold()

qdrant_client = QdrantClient(host=HOST, port=PORT)
embedding_model = SentenceTransformer(MODEL_PATH)
vector_size = embedding_model.get_sentence_embedding_dimension()

if not qdrant_client.collection_exists(collection_name=COLLECTION_NAME):
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
    )
    print(f"[Qdrant] Collection '{COLLECTION_NAME}' created successfully.")
else:
    print(f"[Qdrant] Collection '{COLLECTION_NAME}' already exists.")


def embed_text(text: str) -> list[float]:
    embedding = embedding_model.encode([text], normalize_embeddings=True)
    return embedding[0].tolist() if hasattr(embedding[0], "tolist") else embedding[0]


def test_add_qdrant():
    # Test the Qdrant connection by inserting dummy documents.
    try:
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            wait=True,
            points=[
                models.PointStruct(
                    id=1,
                    vector=embed_text("This is a test defining citrus and their variety."),
                    payload={
                        "source": "test",
                        "id": 1,
                        "description": "This is a test defining citrus and their variety.",
                        "img_path": "/tmp/test_doc_1.jpg",
                    },
                ),
                models.PointStruct(
                    id=2,
                    vector=embed_text("This is another test document describing apples and bananas."),
                    payload={
                        "source": "test2",
                        "id": 2,
                        "description": "This is another test document describing apples and bananas.",
                        "img_path": "/tmp/test_doc_2.jpg",
                    },
                ),
            ],
        )
        results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=embed_text("What is the document most related to oranges?"),
            limit=2,
            with_payload=True,
            with_vectors=False,
        )

        print(f"[Qdrant] Query results: {results}")
        print("[Qdrant] Test documents added successfully.")
    except Exception as e:
        print(f"[Qdrant] Error adding test document: {e}")


def test_query_qdrant():
    # Test the Qdrant query functionality.
    try:
        results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=embed_text("content related to dairy?"),
            limit=3,
            with_payload=True,
            with_vectors=False,
        )

        print(f"[Qdrant] Query results: {results}")

        for point in results.points:
            try:
                doc_metadata = point.payload or {}
                doc_score = point.score

                if doc_score is not None and doc_score >= SIMILARITY_THRESHOLD:
                    doc_id = int(point.id)
                    description = doc_metadata.get("description", None)
                    img_path = doc_metadata.get("img_path", None)

                    print(f"[Qdrant] Document ID: {doc_id}, Description: {description}, Image Path: {img_path}, Score: {doc_score}")
                else:
                    print(f"[Qdrant] Document ID: {point.id}, discarded by similarity score: {doc_score}")
            except Exception as e:
                print(f"[Qdrant] ID is not integer {point.id}: {e}")

    except Exception as e:
        print(f"[Qdrant] Error querying collection: {e}")


def test_query_qdrant_get(id):
    # Test the Qdrant retrieve functionality.
    try:
        results = qdrant_client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[int(id)],
            with_payload=True,
            with_vectors=False,
        )

        print(f"[Qdrant] Retrieve results: {results}")

        for record in results:
            try:
                doc_metadata = record.payload or {}
                doc_id = int(record.id)
                description = doc_metadata.get("description", None)
                img_path = doc_metadata.get("img_path", None)

                print(f"[Qdrant] Document ID: {doc_id}, Description: {description}, Image Path: {img_path}")
            except Exception as e:
                print(f"[Qdrant] ID is not integer {record.id}: {e}")

    except Exception as e:
        print(f"[Qdrant] Error retrieving document: {e}")


if __name__ == "__main__":
    collection_info = qdrant_client.get_collection(collection_name=COLLECTION_NAME)
    print(f"Collection #{COLLECTION_NAME} initialized. Elements: {collection_info.points_count}")

    test_add_qdrant()
    test_query_qdrant()
    test_query_qdrant_get(1)
