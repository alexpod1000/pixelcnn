"""Author: Brandon Trabucco, Copyright 2020, MIT License"""


from pixelcnn.gated_resnet import gated_resnet
from pixelcnn.ops import down_shifted_conv2d
from pixelcnn.ops import down_right_shifted_conv2d
from pixelcnn.ops import down_shifted_conv2d_transpose
from pixelcnn.ops import down_right_shifted_conv2d_transpose
from pixelcnn.ops import down_shift
from pixelcnn.ops import right_shift
from pixelcnn.ops import concat_elu
from tensorflow.keras import layers
from tensorflow.keras import models
import tensorflow as tf


def PixelCNN(
        output_size,
        image_height=32,
        image_width=32,
        image_is_discrete=True,
        num_layers=6,
        filters=256,
        dropout_rate=0.1,
        **kwargs
):
    """Build a Pixel CNN model in Keras.

    Args:
    - output_size: the cardinality of the output vector space.

    - image_height: the height of the images to generate.
    - image_width: the width of the images to generate.
    - image_is_discrete: a boolean that indicates whether
        the image is discrete or continuous features.

    - num_layers: the number of Gated Masked Conv2D layers.

    - filters: the number of filters iun each Conv2D layer.
    - dropout_rate: the fraction of units to drop.

    Returns:
    - model: a Keras model that accepts one tf.int32 tensor
        with shape [batch_dim, image_height, image_width]
    """
    if image_is_discrete:
        images = layers.Input(shape=[image_height, image_width])
    else:
        images = layers.Input(shape=[image_height, image_width, filters])

    #####################################################
    # Embed the discrete image pixels in a vector space #
    #####################################################

    def padding_backend(z):
        return tf.pad(
            z,
            [[0, 0], [0, 0], [0, 0], [0, 1]],
            constant_values=1)

    if image_is_discrete:
        images_embedding = layers.TimeDistributed(
            layers.Embedding(output_size, filters))(images)
    else:
        images_embedding = images
    images_embedding = layers.Lambda(padding_backend)(images_embedding)

    ##############################################
    # Prepare the image for shifted convolutions #
    ##############################################

    top = down_shift(
        down_shifted_conv2d(
            images_embedding, filters, kernel_size=(2, 3)))

    initial_top_left_stream_a = down_shift(
        down_shifted_conv2d(
            images_embedding, filters, kernel_size=(1, 3)))
    initial_top_left_stream_b = right_shift(
        down_right_shifted_conv2d(
            images_embedding, filters, kernel_size=(2, 1)))
    top_left = layers.add([
        initial_top_left_stream_a, initial_top_left_stream_b])

    ###################################################
    # Process with Residual Gated Masked Convolutions #
    ###################################################

    for layer in range(num_layers):

        top = gated_resnet(
            top,
            conv2d=down_shifted_conv2d,
            nonlinearity=concat_elu,
            kernel_size=(2, 3),
            dropout_rate=dropout_rate,
            **kwargs)

        top_left = gated_resnet(
            top_left,
            a=top,
            conv2d=down_right_shifted_conv2d,
            nonlinearity=concat_elu,
            kernel_size=(2, 2),
            dropout_rate=dropout_rate,
            **kwargs)

    #################################################
    # Compute logits for every image pixel location #
    #################################################

    top_left = concat_elu(top_left)
    logits = layers.Conv2D(
        output_size,
        (1, 1),
        strides=(1, 1),
        padding='valid',
        data_format='channels_last',
        **kwargs)(top_left)

    return models.Model(inputs=[images], outputs=logits)


def ConditionalPixelCNN(
        output_size,
        conditional_vector_size,
        image_height=32,
        image_width=32,
        image_is_discrete=True,
        conditional_height=1,
        conditional_width=1,
        class_conditional=True,
        num_classes=None,
        num_preprocess_layers=5,
        num_layers=6,
        filters=256,
        dropout_rate=0.1,
        **kwargs
):
    """Build a Conditional Pixel CNN model in Keras.

    Args:
    - output_size: the cardinality of the output vector space.
    - conditional_vector_size: the cardinality of the vector space
        for conditioning image generation.

    - image_height: the height of the images to generate.
    - image_width: the width of the images to generate.
    - image_is_discrete: a boolean that indicates whether
        the image is discrete or continuous features.

    - conditional_height: the height of the conditional input.
    - conditional_width: the width of the conditional input.
    - class_conditional: a boolean that indicates that
        the conditional inputs are class labels.
    - num_classes: an integer that determines the number
        of unique classes to condition on.

    - num_preprocess_layers: the number of Conv2DTranspose layers
        for upsampling the conditional input.
    - num_layers: the number of Gated Masked Conv2D layers.

    - filters: the number of filters iun each Conv2D layer.
    - dropout_rate: the fraction of units to drop.

    Returns:
    - model: a Keras model that accepts one tf.int32 tensor
        with shape [batch_dim, image_height, image_width] and
        with shape [batch_dim, conditional_height,
            conditional_width, conditional_vector_size]
    """
    if image_is_discrete:
        images = layers.Input(shape=[image_height, image_width])
    else:
        images = layers.Input(shape=[image_height, image_width, filters])
    if class_conditional:
        inputs = layers.Input(shape=[conditional_height, conditional_width])
    else:
        inputs = layers.Input(shape=[
            conditional_height, conditional_width, conditional_vector_size])

    #####################################################
    # Upsample the conditional inputs to the image size #
    #####################################################

    conditional_embedding = inputs
    if class_conditional:
        conditional_embedding = layers.TimeDistributed(
            layers.Embedding(
                num_classes, conditional_vector_size))(conditional_embedding)

    for i in range(num_preprocess_layers):
        if i > 0:
            conditional_embedding = concat_elu(conditional_embedding)
        conditional_embedding = layers.Conv2DTranspose(
            filters,
            (5, 5),
            strides=(2, 2),
            padding='same',
            data_format='channels_last',
            **kwargs)(conditional_embedding)

    #####################################################
    # Embed the discrete image pixels in a vector space #
    #####################################################

    def padding_backend(z):
        return tf.pad(
            z,
            [[0, 0], [0, 0], [0, 0], [0, 1]],
            constant_values=1)

    if image_is_discrete:
        images_embedding = layers.TimeDistributed(
            layers.Embedding(output_size, filters))(images)
    else:
        images_embedding = images
    images_embedding = layers.Lambda(padding_backend)(images_embedding)

    ##############################################
    # Prepare the image for shifted convolutions #
    ##############################################

    top = down_shift(
        down_shifted_conv2d(
            images_embedding, filters, kernel_size=(2, 3)))

    initial_top_left_stream_a = down_shift(
        down_shifted_conv2d(
            images_embedding, filters, kernel_size=(1, 3)))
    initial_top_left_stream_b = right_shift(
        down_right_shifted_conv2d(
            images_embedding, filters, kernel_size=(2, 1)))
    top_left = layers.add([
        initial_top_left_stream_a, initial_top_left_stream_b])

    ###################################################
    # Process with Residual Gated Masked Convolutions #
    ###################################################

    for layer in range(num_layers):

        top = gated_resnet(
            top,
            h=conditional_embedding,
            conv2d=down_shifted_conv2d,
            nonlinearity=concat_elu,
            kernel_size=(2, 3),
            dropout_rate=dropout_rate,
            **kwargs)

        top_left = gated_resnet(
            top_left,
            a=top,
            h=conditional_embedding,
            conv2d=down_right_shifted_conv2d,
            nonlinearity=concat_elu,
            kernel_size=(2, 2),
            dropout_rate=dropout_rate,
            **kwargs)

    #################################################
    # Compute logits for every image pixel location #
    #################################################

    top_left = concat_elu(top_left)
    logits = layers.Conv2D(
        output_size,
        (1, 1),
        strides=(1, 1),
        padding='valid',
        data_format='channels_last',
        **kwargs)(top_left)

    return models.Model(inputs=[images, inputs], outputs=logits)
