"""Author: Brandon Trabucco, Copyright 2020, MIT License"""


from pixelcnn import ConditionalPixelCNNPlusPlus
import tensorflow_datasets as tfds
import tensorflow as tf


if __name__ == "__main__":

    tf.io.gfile.makedirs("models")

    model = ConditionalPixelCNNPlusPlus(
        1000,
        32,
        image_height=32,
        image_width=32,
        conditional_height=1,
        conditional_width=1,
        num_preprocess_layers=5,
        num_modules=3,
        num_layers_per_module=6,
        filters=64,
        dropout_rate=0.1,
        class_conditional=True,
        num_classes=10)

    optimizer = tf.keras.optimizers.Adam()

    train_ds = tfds.load("cifar10", split="train")
    train_ds = train_ds.shuffle(1024).batch(32).repeat(5)
    train_ds = train_ds.prefetch(10)

    for i, example in enumerate(train_ds):

        images = tf.cast(tf.cast(
            example["image"], tf.float32) / 25.6, tf.int32)

        images = (images[:, :, :, 0] +
                  images[:, :, :, 1] * 10 +
                  images[:, :, :, 2] * 100)

        labels = tf.cast(
            example["label"], tf.int32)[:, tf.newaxis, tf.newaxis]

        def loss_function():

            bits_per_dim = tf.reduce_mean(
                tf.keras.losses.sparse_categorical_crossentropy(
                    images, model([images, labels]), from_logits=True))

            tf.print("Iteration:", i, "Bits Per Dim:", bits_per_dim)

            return bits_per_dim

        optimizer.minimize(loss_function, model.trainable_variables)

        if i % 100 == 0:
            model.save('models/model.h5')
