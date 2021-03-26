# -*- coding: utf-8 -*-
"""
Created on Thu May 21 17:42:15 2020

@author: Sarah
"""
import torch
from torch.utils.data import Dataset
import os
from skimage import io
from torchvision.datasets.utils import download_url
import zipfile
import json
from skimage.transform import rescale


def convert_item_to_encoded_item(item):

    encoded_item = []

    minecraft_item_names = [
        'anvil', 'beacon', 'bed', 'bedrock', 'bookshelf', 'brewing_stand',
        'cactus', 'cake', 'cauldron', 'clay', 'coal_block', 'cobblestone',
        'crafting_table', 'daylight_detector', 'deadbush', 'diamond_block',
        'dirt', 'dispenser', 'dropper', 'emerald_block', 'enchanting_table',
        'glowstone', 'gravel', 'hopper', 'ice', 'iron_block', 'jukebox',
        'lapis_block', 'leaves', 'lever', 'log', 'mycelium', 'netherrack',
        'noteblock', 'obsidian', 'piston', 'planks', 'prismarine', 'pumpkin',
        'quartz_block', 'reeds', 'sand', 'sandstone', 'sapling', 'sea_lantern',
        'slime', 'snow', 'soul_sand', 'sponge', 'stone', 'stonebrick',
        'tallgrass', 'tnt', 'torch', 'vine', 'waterlily', 'web', 'wheat', 'wool'
    ]
    minecraft_item_names = ["minecraft:" + name for name in minecraft_item_names]

    for item_name in minecraft_item_names:
        if item_name == item:
            encoded_item.append(1)
        else:
            encoded_item.append(0)

    return encoded_item


def nov_dict_to_encoded_nov(json):

    vector = [[], []]
    encoded_item = []

    # First check if we have a novelty described in the json file:
    if bool(json):

        if json['novelty'][0]['noveltyType'] == 'NewItem':
            vector[0].append(1)
            item = json['novelty'][0]['noveltyItem']
            encoded_item = convert_item_to_encoded_item(item)
            vector[1].append(encoded_item)

        if json['novelty'][0]['noveltyType'] == 'newPosition':
            vector[0].append(2)

    else:

        vector[0].append(0)

    return vector


def count_png_in_env(path, env_name, env_idx):

    img_ctr = 0

    with zipfile.ZipFile(path, 'r') as zip:
        file_names = zip.namelist()

        for file_name in file_names:

            # We need the path separation symbol in order to not count
            # environemnts which only contain the env_idx (4 --> 41)
            if file_name.find(env_name + str(env_idx) + '/') != -1 or \
                    file_name.find(env_name + str(env_idx) + '\\') != -1:

                if file_name.find('.png') != -1:

                    img_ctr += 1

    return img_ctr


def preprocess_image(image, scale_factor, p_size):
    image = crop_and_scale(image, scale_factor)
    image = extract_patches(image, p_size)
    return image


def crop_and_scale(image, scale_factor):

    image = image[0:234, :, :]
    image = rescale(image, (scale_factor, scale_factor, 1), anti_aliasing=True)

    return image


def extract_patches(image, p_size):

    # Extract patches
    stride = int(p_size/2)  # patch stride
    image = torch.from_numpy(image)
    patches = image.unfold(0, p_size, stride).unfold(1, p_size, stride)

    return patches


class PolycraftDataset(Dataset):

    def __init__(self, nov_type, noi, env_idx, p_size, scale_factor):

        self.nov_type = nov_type
        self.allpatches = []
        self.allnovbins = []
        self.all_images = []

        self.root_normal = 'datasets' + os.sep + 'normal_data'
        self.filename_normal = 'normal_data.zip'

        self.root_nov = 'datasets' + os.sep + 'novel_data'
        self.filename_nov_item = 'item_novelty.zip'
        self.filename_nov_height = 'height_novelty.zip'

        self.path_normal = self.root_normal + os.sep + self.filename_normal
        self.path_nov_item = self.root_nov + os.sep + self.filename_nov_item
        self.path_nov_height = self.root_nov + os.sep + self.filename_nov_height

        self.scale_factor = scale_factor
        self.p_size = p_size

        # print('path_normal', self.path_normal) #\\

        nov_dict = {}
        old_img = []

        find_json = False
        find_png = False

        # Load zipped files from BOX
        path, root, env_name = self.load_zipped_files()

        noi_check = count_png_in_env(path, env_name, env_idx)

        # Check if there are noi images in the environment, if not use the maximum number
        if(noi >= noi_check):
            noi = noi_check
            print('noi and/or noe too large, all available images are used.')

        ctr = 0

        while (ctr < noi):

            ctr += 1

            with zipfile.ZipFile(path, 'r') as zip:
                file_names = zip.namelist()

                for file_name in file_names:

                    if file_name.find(env_name + str(env_idx)) != -1:

                        # Unzip novelty description file
                        if file_name.find('novelty_description.json') != -1:

                            zip.extract(file_name, root)
                            json_path = root + os.sep + file_name
                            # print(json_path)
                            find_json = True

                            with open(json_path) as json_file:
                                nov_dict = json.load(json_file)

                        # Unzip  images
                        if file_name.find('.png') != -1:

                            if file_name not in old_img:
                                old_img.append(file_name)

                                zip.extract(file_name, root)
                                find_png = True

                                # Read image, remove "Minecraft score bar", rescale
                                png_path = root + os.sep + file_name
                                image = io.imread(png_path)  # Height x Width x RGB Channels
                                patches = preprocess_image(image, self.scale_factor, self.p_size)

                                # Convert novelty description json file to encoded vector
                                nov_vector = nov_dict_to_encoded_nov(nov_dict)

                                break

            if not find_png and not find_json:
                print('-----------------------')
                print('Files not found, check if environemnt exists!')
                print('-----------------------')

            self.allpatches.append(patches)
            self.allnovbins.append(nov_vector)
            self.all_images.append(image)

    def __len__(self):

        # Total number of images
        return len(self.allpatches)

    def __getitem__(self, index):

        return(self.allpatches[index], self.allnovbins[index], self.all_images[index])

    def load_zipped_files(self):
        if self.nov_type == 'normal':

            url_normal_data = 'https://tufts.box.com/shared/static/t5s7pss0het9p2n1wp81f1ewonyk99hm.zip'
            download_url(url_normal_data, self.root_normal, self.filename_normal)
            path = self.path_normal
            root = self.root_normal
            env_name = 'env_'

        elif self.nov_type == 'novel_item':
            url_nov_item = 'https://tufts.box.com/shared/static/7dow5ah9anotzmqncw7z7ey83t09sfny.zip'
            download_url(url_nov_item, self.root_nov, self.filename_nov_item)
            path = self.path_nov_item
            root = self.root_nov
            env_name = 'novelty_'

        elif self.nov_type == 'novel_height':

            url_nov_height = 'https://tufts.box.com/shared/static/3k85fitc1t50i8t0ez6nl5rlw807ruib.zip'
            download_url(url_nov_height, self.root_nov, self.filename_nov_height)
            path = self.path_nov_height
            root = self.root_nov
            env_name = 'novelty_'

        else:
            print('No valid novelty type!')

        return path, root, env_name
