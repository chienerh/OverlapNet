#!/usr/bin/env python3
# Developed by Xieyuanli Chen and Thomas Läbe
# This file is covered by the LICENSE file in the root of this project.
# Brief: A generator which generates batches for keras training: Special version
import os
import random
import numpy as np

from keras.utils import Sequence


class ImagePairOverlapFunctionAngleOrientationSequence(Sequence):
  """ This class is responsible for loading training/validation data. It
      can be used as keras generator object in e.g. model.fit_generator.
  """
  
  def __init__(self, image_path, imgfilenames1, imgfilenames2, dir1, dir2, overlap, function_angle, orientation,
               network_output_size, batch_size, height, width, no_channels=4,
               use_depth=True, use_normals=True, use_class_probabilities=False, use_class_probabilities_pca=False,
               use_intensity=False, rotate_data=0):
    """ Initialize the dataset.
      Args:
        image_patch: Path where to find all the images. This is the folder which
                     includes the subfolders 'depth_data', 'normal_data', 'semantic_data', ...
        imgfilenames1, imgfilenames2: a list of filenames of the images. If
                                      imgfilenames2 is empty, only one leg is
                                      assumed and will be generated by __getitem__()
        imgfilename1[i] and imgfilename2[i] build a pair.
        dir1, dir2: sequence directory names for imgfilenames1, imgfilenames2.
                    Two lists of the same size as imgfilenames1 and imgfilenames2
                    which contain the name of the dataset directory. e.g.
                    dir1[0]/depth_data/imgfilenames1[0].png
        overlap: true ouput: a nx1 numpy array with the overlap (0..1). Same length as
                 imgfilename1 and imgfilename2
        function_angle: true ouput2: a nx1 numpy array with the function angle (0..1). Same length as
                 imgfilename1 and imgfilename2
        orientation: true output position of the peak in the network output which shows the relative rotation of
                     the pair (around vertical axis). nx1, same length as overlap
        network_output_size: The network puts out a 1xM vector with ideally one peak, M is given here                     
        height and width: size of the input images of the network
        no_channels: number of channels of the input of the network, default 4
        use_depth, use_normals, use_class_probabilities: Booleans which define
            whether to use depth, normals, class probabilies. Defaults: True, True, False
        rotate_data:
            0: no rotation
            1: rotate every "right" image of a pair randomly between 0 and 360
               (That actually means shift the image). The sequence of random rotations
               is the same for every epoch, thus every pair is shifted always with the
               same amount.
            2: rotate every "right" image of a pair randomly between 0 and 360
               (That actually means shift the image). Use a different shift for different
               epochs even for the same pair. The sequence of random numbers is mainly the
               same every time this class is initialized. (Due to threading, it may
               change for some pairs)
            Default:0
    """
    self.image_path = image_path
    self.batch_size = batch_size
    self.imgfilenames1 = imgfilenames1
    self.imgfilenames2 = imgfilenames2
    self.dir1 = dir1
    self.dir2 = dir2
    self.overlap = overlap
    self.function_angle = function_angle
    self.orientation = orientation
    self.network_output_size = network_output_size
    # number of pairs
    self.n = overlap.size
    self.height = height
    self.width = width
    self.no_channels = no_channels
    self.use_depth = use_depth
    self.use_normals = use_normals
    self.use_class_probabilities = use_class_probabilities
    self.use_class_probabilities_pca = use_class_probabilities_pca
    self.use_intensity = use_intensity
    self.rotate_data = rotate_data
    self.do_rotation = False
    if self.rotate_data > 0:
      random.seed(1234)
      self.do_rotation = True
      self.random_rotate = np.array([
        random.randint(0, self.width) for i in range(0, self.n)])
  
  def __len__(self):
    """ Returns number of batches in the sequence. (overwritten method)
    """
    return int(np.ceil(self.n / float(self.batch_size)))
  
  def __getitem__(self, idx):
    """ Get a batch. (overwritten method)
    """
    if idx == 0 and self.rotate_data == 2:
      # new random values
      self.random_rotate = np.array([
        random.randint(0, self.width) for i in range(0, self.n)])
    
    maxidx = (idx + 1) * self.batch_size
    size = self.batch_size
    if maxidx > self.n:
      maxidx = self.n
      size = maxidx - idx * self.batch_size
    batch_f1 = self.imgfilenames1[idx * self.batch_size: maxidx]
    dir_f1 = self.dir1[idx * self.batch_size: maxidx]
    x1 = np.zeros((size, self.height, self.width, self.no_channels))
    
    if self.imgfilenames2:
      batch_f2 = self.imgfilenames2[idx * self.batch_size: maxidx]
      dir_f2 = self.dir2[idx * self.batch_size: maxidx]
      x2 = np.zeros((size, self.height, self.width, self.no_channels))
    
    for i in range(0, size):
      self.prepareOneInput(x1, i, batch_f1, dir_f1)
      if self.imgfilenames2:
        self.prepareOneInput(x2, i, batch_f2, dir_f2, idx * size + i, self.do_rotation)
    
    y_overlap = self.overlap[idx * self.batch_size: maxidx]
    y_function_angle = self.function_angle[idx * self.batch_size: maxidx]
    y_orientation = self.orientation[idx * self.batch_size: maxidx]
    y = []
    
    for idx in range(len(y_overlap)):
      y_item = np.zeros(self.network_output_size)
      y_item[int(y_orientation[idx])] = y_function_angle[idx] # y_overlap[idx]
      y.append(y_item)
    
    y = np.asarray(y)
    
    if self.imgfilenames2:
      return ([x1, x2], [np.hstack(y_overlap, y_function_angle), y])
    else:
      return ([x1], y)
  
  def prepareOneInput(self, x1, i, batch_f1, dir_f1, totalidx=0, rotate_data=False):
    """ Internal function to generate input for one set of images
        Args:
          x1: n x w x h x chan array: The complete input. (input and ouput)
           i: The index (first dimension of x1) where to put the current image set
           batch_f1: filename prefixes of the current batch. batch_f1[i] is used.
           dir_f1  : dataset directory names for batch_f1
           totalidx: the current index in the whole set of pairs, Used only for
                     rotate_data.
           rotate_data: If True, the output is shifted along width axis arbitrarly
        Returns: nothing, output is in x1
    """
    channelidx = 0
    if self.use_depth:
      # Depth map == first channel
      f = os.path.join(self.image_path, dir_f1[i], 'depth', batch_f1[i] + '.npy')
      try:
        img1 = np.load(f)
      except IOError:  
        raise Exception('Could not read depth image %s' % f)
      
      x1[i, :, :, channelidx] = img1
      channelidx += 1
    
    if self.use_normals:
      # normal map == channel 1..3
      f = os.path.join(self.image_path, dir_f1[i], 'normal', batch_f1[i] + '.npy')
      try:
        img1 = np.load(f)
      except IOError:  
          raise Exception('Could not read normal image %s' % f)
        
      x1[i, :, :, channelidx:channelidx+3] = img1
      channelidx += 3
    
    if self.use_class_probabilities:
      if self.use_class_probabilities_pca:
        f = os.path.join(self.image_path, dir_f1[i], 'probability_pca', batch_f1[i] + '.npy')
      else:
        f = os.path.join(self.image_path, dir_f1[i], 'probability', batch_f1[i] + '.npy')
      
      try:
        img1 = np.load(f)

        if self.use_class_probabilities_pca:
          x1[i, :, :, channelidx:channelidx + 3] = img1
          channelidx += 3
        else:
          x1[i, :, :, channelidx:channelidx + 20] = img1
          channelidx += 20
      
      except IOError:
        # Try to read format .npz
        if self.use_class_probabilities_pca:
          f = os.path.join(self.image_path, dir_f1[i], 'probability_pca', batch_f1[i] + '.npz')
        else:
          f = os.path.join(self.image_path, dir_f1[i], 'probability', batch_f1[i] + '.npz')
        
        img1 = np.load(f)

        if self.use_class_probabilities_pca:
          x1[i, :, :, channelidx:channelidx + 3] = img1
          channelidx += 3
        else:
          x1[i, :, :, channelidx:channelidx + 20] = img1
          channelidx += 20

    if self.use_intensity:
      f = os.path.join(self.image_path, dir_f1[i], 'intensity', batch_f1[i] + '.npy')
      try:
        img1 = np.load(f)
      except IOError:
        # Try to read format .npz
        f = os.path.join(self.image_path, dir_f1[i], 'intensity', batch_f1[i] + '.npz')
        img1 = np.load(f)

      x1[i, :, :, channelidx] = img1
      channelidx += 1
      
    if rotate_data:
      shift = self.random_rotate[totalidx]
      # print("totalidx: %3d  shift %3d" % (totalidx, shift))
      x1[i, :, :, :] = np.roll(x1[i, :, :, :], shift, axis=1)
