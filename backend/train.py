"""Train a MobileNetV2-based real/fake Indian currency classifier.

Expected dataset layout (folder names become the classes):

    data/dataset/
        real/
            *.jpg
        fake/
            *.jpg

Usage:
    python -m backend.train --data data/dataset --epochs 12 --fine-tune
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

IMG_SIZE = 224


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/dataset"))
    parser.add_argument(
        "--output", type=Path, default=Path("models/currency_model.keras")
    )
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--fine-tune-epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--validation-split", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--fine-tune",
        action="store_true",
        help="Unfreeze the last MobileNetV2 block and fine-tune it.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import numpy as np
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from tensorflow.keras.applications import MobileNetV2

    if not args.data.is_dir():
        raise SystemExit(
            f"Dataset folder not found: {args.data}\n"
            "Create data/dataset/real/ and data/dataset/fake/ and add images."
        )

    train_ds = keras.utils.image_dataset_from_directory(
        args.data,
        validation_split=args.validation_split,
        subset="training",
        seed=args.seed,
        image_size=(IMG_SIZE, IMG_SIZE),
        batch_size=args.batch_size,
        label_mode="categorical",
    )
    val_ds = keras.utils.image_dataset_from_directory(
        args.data,
        validation_split=args.validation_split,
        subset="validation",
        seed=args.seed,
        image_size=(IMG_SIZE, IMG_SIZE),
        batch_size=args.batch_size,
        label_mode="categorical",
    )

    class_names = train_ds.class_names
    if len(class_names) != 2:
        raise SystemExit(
            "Expected exactly two class folders (for example real/ and fake/), "
            f"but found: {class_names}"
        )

    print(f"Classes: {class_names}")
    for name in class_names:
        count = sum(1 for path in (args.data / name).glob("*") if path.is_file())
        print(f"  {name}: {count} images")

    autotune = tf.data.AUTOTUNE
    train_ds = train_ds.prefetch(autotune)
    val_ds = val_ds.prefetch(autotune)

    augmentation = keras.Sequential(
        [
            layers.RandomFlip("horizontal"),
            layers.RandomRotation(0.04),
            layers.RandomZoom(0.1),
            layers.RandomContrast(0.1),
        ],
        name="augmentation",
    )

    base_model = MobileNetV2(
        input_shape=(IMG_SIZE, IMG_SIZE, 3),
        include_top=False,
        weights="imagenet",
    )
    base_model.trainable = False

    inputs = keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3), name="note_image")
    x = augmentation(inputs)
    x = layers.Rescaling(1.0 / 127.5, offset=-1.0, name="mobilenet_preprocess")(x)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(2, activation="softmax", name="prediction")(x)

    model = keras.Model(inputs, outputs, name="fake_currency_detector")

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.summary()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    callbacks = [
        keras.callbacks.ModelCheckpoint(
            filepath=str(args.output),
            monitor="val_accuracy",
            save_best_only=True,
            verbose=1,
        ),
        keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=4,
            restore_best_weights=True,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.3,
            patience=2,
            verbose=1,
        ),
    ]

    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        callbacks=callbacks,
    )

    if args.fine_tune and args.fine_tune_epochs > 0:
        print("\nFine-tuning the last MobileNetV2 block...")
        base_model.trainable = True
        for layer in base_model.layers[:-30]:
            layer.trainable = False

        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=1e-5),
            loss="categorical_crossentropy",
            metrics=["accuracy"],
        )
        model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=args.epochs + args.fine_tune_epochs,
            initial_epoch=len(history.epoch),
            callbacks=[
                keras.callbacks.EarlyStopping(
                    monitor="val_accuracy",
                    patience=3,
                    restore_best_weights=True,
                ),
                keras.callbacks.ReduceLROnPlateau(
                    monitor="val_loss",
                    factor=0.3,
                    patience=2,
                    verbose=1,
                ),
            ],
        )

    loss, accuracy = model.evaluate(val_ds, verbose=0)
    print(f"\nValidation accuracy: {accuracy:.2%} (loss {loss:.4f})")

    y_true: list[int] = []
    y_pred: list[int] = []
    for images, labels in val_ds:
        probabilities = model.predict(images, verbose=0)
        y_true.extend(np.argmax(labels.numpy(), axis=1).tolist())
        y_pred.extend(np.argmax(probabilities, axis=1).tolist())

    matrix = np.zeros((2, 2), dtype=int)
    for true_label, predicted_label in zip(y_true, y_pred):
        matrix[true_label][predicted_label] += 1

    print("\nConfusion matrix (rows = true, columns = predicted):")
    print(f"{'':>10}{class_names[0]:>12}{class_names[1]:>12}")
    for index, name in enumerate(class_names):
        print(f"{name:>10}{matrix[index][0]:>12}{matrix[index][1]:>12}")

    model.save(str(args.output))
    meta_path = args.output.parent / "class_names.json"
    meta_path.write_text(
        json.dumps(
            {
                "class_names": class_names,
                "image_size": IMG_SIZE,
                "input": "RGB 0-255",
                "preprocessing": "rescale to [-1, 1] inside the model",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nSaved model to: {args.output}")
    print(f"Saved metadata to: {meta_path}")
    print("Restart the web server to load the new model.")


if __name__ == "__main__":
    main()
