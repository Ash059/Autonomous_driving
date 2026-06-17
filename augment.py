import cv2
import pandas as pd
import numpy as np
import os

# Paths
DATASET_DIR = "driving_dataset"
CSV_PATH = os.path.join(DATASET_DIR, "driving_log.csv")
AUG_CSV_PATH = os.path.join(DATASET_DIR, "augmented_driving_log.csv")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")

def augment_brightness(image):
    """Randomly adjust brightness."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    ratio = 1.0 + 0.4 * (np.random.rand() - 0.5) # Scale brightness by 0.8 to 1.2
    hsv[:,:,2] = np.clip(hsv[:,:,2] * ratio, 0, 255)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

def main():
    print("Loading original dataset...")
    df = pd.read_csv(CSV_PATH)
    augmented_data = []

    for index, row in df.iterrows():
        img_path = os.path.join(DATASET_DIR, row['image_path'])
        steering = float(row['steering_angle'])
        throttle = float(row['throttle'])

        image = cv2.imread(img_path)
        if image is None:
            continue

        # 1. Keep original
        augmented_data.append([row['image_path'], steering, throttle])

        # 2. Add Brightness Variation (to original)
        bright_img = augment_brightness(image)
        bright_name = f"bright_{os.path.basename(img_path)}"
        cv2.imwrite(os.path.join(IMAGES_DIR, bright_name), bright_img)
        augmented_data.append([os.path.join("images", bright_name), steering, throttle])

        # 3. Horizontal Flip
        flipped_img = cv2.flip(image, 1) # 1 = horizontal flip
        flipped_steering = steering * -1.0 # Reverse the steering!
        
        flip_name = f"flip_{os.path.basename(img_path)}"
        cv2.imwrite(os.path.join(IMAGES_DIR, flip_name), flipped_img)
        augmented_data.append([os.path.join("images", flip_name), flipped_steering, throttle])

        if index % 1000 == 0 and index > 0:
            print(f"Processed {index} original images...")

    # Save the massive new dataset
    aug_df = pd.DataFrame(augmented_data, columns=['image_path', 'steering_angle', 'throttle'])
    aug_df.to_csv(AUG_CSV_PATH, index=False)
    print(f"Done! Dataset expanded to {len(aug_df)} images.")

if __name__ == "__main__":
    main()