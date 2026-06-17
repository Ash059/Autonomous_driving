import os
import pandas as pd
import tensorflow as tf
from sklearn.model_selection import train_test_split
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, Flatten, Dense, Dropout, Lambda
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping

# --- 1. Configuration ---
DATASET_DIR = "driving_dataset"
CSV_PATH = os.path.join(DATASET_DIR, "augmented_driving_log.csv")
BATCH_SIZE = 64
EPOCHS = 30

def main():
    # --- 2. Load and Prepare the Data ---
    print("Loading CSV...")
    df = pd.read_csv(CSV_PATH)

    # Prepend the directory to the relative paths in your CSV
    # Prepend the directory and force Linux-style forward slashes
    image_paths = df['image_path'].apply(lambda x: os.path.join(DATASET_DIR, str(x).replace('\\', '/'))).values
    
    # Target values: We are predicting TWO things simultaneously
    labels = df[['steering_angle', 'throttle']].values

    # Split: 80% for learning, 20% for the final exam
    X_train, X_val, y_train, y_val = train_test_split(image_paths, labels, test_size=0.2, random_state=42)
    print(f"Training on {len(X_train)} images, Validating on {len(X_val)} images.")

    # --- 3. The High-Speed Data Conveyor Belt ---
    def process_image(img_path, label):
        img_raw = tf.io.read_file(img_path)
        img = tf.image.decode_jpeg(img_raw, channels=3)
        img = tf.reshape(img, [240, 320, 3]) # Force exact dimensions
        img = tf.cast(img, tf.float32)
        return img, label

    # Autotune allows TensorFlow to dynamically manage CPU threads for max speed
    train_ds = tf.data.Dataset.from_tensor_slices((X_train, y_train))
    train_ds = train_ds.shuffle(10000).map(process_image, num_parallel_calls=tf.data.AUTOTUNE)
    train_ds = train_ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

    val_ds = tf.data.Dataset.from_tensor_slices((X_val, y_val))
    val_ds = val_ds.map(process_image, num_parallel_calls=tf.data.AUTOTUNE)
    val_ds = val_ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

    # --- 4. The NVIDIA Dave-2 Architecture ---
    print("Building Neural Network...")
    model = Sequential([
        # Image Normalization (0 to 255 -> -0.5 to 0.5) 
        # Built directly into the model so we don't have to do it manually during live driving!
        Lambda(lambda x: x / 255.0 - 0.5, input_shape=(240, 320, 3)),
        
        # Extracting Road Features
        Conv2D(24, (5, 5), strides=(2, 2), activation='elu'),
        Conv2D(36, (5, 5), strides=(2, 2), activation='elu'),
        Conv2D(48, (5, 5), strides=(2, 2), activation='elu'),
        Conv2D(64, (3, 3), activation='elu'),
        Conv2D(64, (3, 3), activation='elu'),
        
        # Forgetting 50% of connections randomly to prevent memorizing the room
        Dropout(0.5),
        Flatten(),
        
        # Translating features into physical driving commands
        Dense(100, activation='elu'),
        Dense(50, activation='elu'),
        Dense(10, activation='elu'),
        
        # Output: [Steering, Throttle]
        Dense(2, activation='linear')
    ])
    
    # We use a lower learning rate (1e-4) so it learns smoothly without erratic jumps
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4), loss='mse')
    model.summary()

    # --- 5. The Safety Nets ---
    # Always save the absolute best version of the brain
    checkpoint = ModelCheckpoint('autodrive_model.keras', monitor='val_loss', save_best_only=True, verbose=1)
    
    # If the network stops getting smarter for 5 rounds, pull the plug early
    early_stop = EarlyStopping(monitor='val_loss', patience=5, verbose=1)

    # --- 6. Start the Engine ---
    print("\nStarting Training Session. Listen for the GPU fans...\n")
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=EPOCHS,
        callbacks=[checkpoint, early_stop]
    )

    print("\nTraining Complete! The brain is successfully saved as 'autodrive_model.keras'.")

if __name__ == "__main__":
    main()