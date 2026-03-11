from backend.app.config import DATA_PATH
from backend.app.data_loader import generate_synthetic_dataset


if __name__ == "__main__":
    frame = generate_synthetic_dataset(DATA_PATH)
    print(f"Generated {len(frame)} rows at {DATA_PATH}")
