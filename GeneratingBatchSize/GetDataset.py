﻿from utils import preprocessing
import tensorflow as tf
import os

# Randomly crop or pad a [_HEIGHT, _WIDTH] section of the image and label.
_HEIGHT = 1000
_WIDTH = 1000

# image chanel
_DEPTH = 3

#  Randomly scale the image and label
_MIN_SCALE = 0.5
_MAX_SCALE = 2.0

# 忽略标签
_IGNORE_LABEL = 255

_NUM_IMAGES = {
    'train': 5000,
    'validation': 500
}
def get_filenames(is_training, data_dir):
  """Return a list of filenames.

  Args:
    is_training: A boolean denoting whether the input is for training.
    data_dir: path to the the directory containing the input data.

  Returns:
    A list of file names.
  """
  if is_training:
    return [os.path.join(data_dir, 'train3.tfrecord')]
  else:
    return [os.path.join(data_dir, 'val3.tfrecord')]


def parse_record(raw_record):
    """Parse PASCAL image and label from a tf record."""
    features = tf.parse_single_example(
      raw_record, features={
          'data': tf.FixedLenFeature([], tf.string),
          'label': tf.FixedLenFeature([], tf.string),
      })

    image = tf.decode_raw(features['data'], tf.uint8)
    image = tf.reshape(image, [1000, 1000, 4])
    image = tf.cast(image, dtype=tf.float32)

    image = tf.gather(image, [0, 1, 2], axis=2)
    # 减去均值
    image_reshape = tf.reshape(image, [1000000, 3])
    mean = tf.reduce_mean(image_reshape, 0)
    image = image - mean
    label = tf.decode_raw(features['label'], tf.uint8)
    label = tf.reshape(label, [1000, 1000, 1])
    label = tf.cast(label, dtype=tf.int32)

    return image, label

def preprocess_image(image, label, is_training):
  """Preprocess a single image of layout [height, width, depth]."""
  if is_training:
    # Randomly scale the image and label.
    image, label = preprocessing.random_rescale_image_and_label(image, label, _MIN_SCALE, _MAX_SCALE)

    # Randomly crop or pad a [_HEIGHT, _WIDTH] section of the image and label.
    image, label = preprocessing.random_crop_or_pad_image_and_label(image, label, _HEIGHT, _WIDTH, _IGNORE_LABEL)

    # Randomly flip the image and label horizontally.
    image, label = preprocessing.random_flip_left_right_image_and_label(
        image, label)

    image.set_shape([_HEIGHT, _WIDTH, 3])
    label.set_shape([_HEIGHT, _WIDTH, 1])

  #image = preprocessing.mean_image_subtraction(image)

  return image, label

def train_or_eval_input_fn(is_training, data_dir, batch_size, num_epochs=None):
    """Input_fn using the tf.data input pipeline for CIFAR-10 dataset.

    Args:
    is_training: A boolean denoting whether the input is for training.
    data_dir: The directory containing the input data.
    batch_size: The number of samples per batch.
    num_epochs: The number of epochs to repeat the dataset.

    Returns:
    A tuple of images and labels.
    """
    dataset = tf.data.Dataset.from_tensor_slices(get_filenames(is_training, data_dir))
    dataset = dataset.flat_map(tf.data.TFRecordDataset)

    if is_training:
        dataset = dataset.shuffle(buffer_size=500)

    dataset = dataset.map(parse_record)
    dataset = dataset.map(
        lambda image, label: preprocess_image(image, label, is_training))
    dataset = dataset.prefetch(batch_size)

    # We call repeat after shuffling, rather than before, to prevent separate
    # epochs from blending together.
    dataset = dataset.repeat(num_epochs)
    dataset = dataset.batch(batch_size)

    return dataset

def eval_or_test_input_fn(image_filenames, label_filenames=None, batch_size=1):
  """An input function for evaluation and inference.

  Args:
    image_filenames: The file names for the inferred images.
    label_filenames: The file names for the grand truth labels.
    batch_size: The number of samples per batch. Need to be 1
        for the images of different sizes.

  Returns:
    A tuple of images and labels.
  """
  # Reads an image from a file, decodes it into a dense tensor
  def _parse_function(filename, is_label):
    if not is_label:
      image_filename, label_filename = filename, None
    else:
      image_filename, label_filename = filename

    image_string = tf.read_file(image_filename)
    image = tf.image.decode_image(image_string)
    image = tf.to_float(tf.image.convert_image_dtype(image, dtype=tf.uint8))
    image.set_shape([None, None, 4])

    image = preprocessing.mean_image_subtraction(image)

    if not is_label:
      return image
    else:
      label_string = tf.read_file(label_filename)
      label = tf.image.decode_image(label_string)
      label = tf.to_int32(tf.image.convert_image_dtype(label, dtype=tf.uint8))
      label.set_shape([None, None, 1])

      return image, label

  if label_filenames is None:
    input_filenames = image_filenames
  else:
    input_filenames = (image_filenames, label_filenames)

  dataset = tf.data.Dataset.from_tensor_slices(input_filenames)
  if label_filenames is None:
    dataset = dataset.map(lambda x: _parse_function(x, False))
  else:
    dataset = dataset.map(lambda x, y: _parse_function((x, y), True))
  dataset = dataset.prefetch(batch_size)
  dataset = dataset.batch(batch_size)
  iterator = dataset.make_one_shot_iterator()

  if label_filenames is None:
    images = iterator.get_next()
    labels = None
  else:
    images, labels = iterator.get_next()

  return images, labels
