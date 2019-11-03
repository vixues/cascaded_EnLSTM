import numpy as np
import torch.utils.data
import pandas as pd
from sklearn import preprocessing
import torch

# NOTE:
#   Record TRAIN_ID and TEST_ID if you change them
WELL = 14
HEAD = ['DEPTH', 'BRITTLE_HORZ', 'BRITTLE_VERT', 'COHESION', 'DEN', 'DTC', 'E_HORZ', 'E_VERT', 'GGRM',
        'GMPO', 'GMTH', 'GMUR', 'MSPD', 'NPRL', 'PF', 'PP', 'PR_HORZ', 'PR_VERT', 'R20F', 'R30F', 'R40F',
        'R60F', 'R85F', 'SHDEF','SHMAX', 'SHMIN', 'ST', 'SV', 'TOC', 'UCS', 'VP', 'VPVS_X', 'VPVS_Y',
        'VS_X', 'VS_Y']
COLUMNS = ['DEPTH', 'GGRM', 'GMPO', 'GMTH', 'GMUR', 'MSPD',  'R20F', 'R85F', 'VP', 'VS_X', 'VS_Y',
           'E_HORZ', 'E_VERT','COHESION', 'UCS','DEN', 'ST', 'BRITTLE_HORZ', 'BRITTLE_VERT', 'PR_HORZ', 'PR_VERT', 'NPRL', 'TOC']


COLUMNS_TARGET = ['E_HORZ', 'E_VERT','COHESION', 'UCS', 'DEN', 'ST', 'BRITTLE_HORZ', 'BRITTLE_VERT', 'PR_HORZ', 'PR_VERT', 'NPRL', 'TOC']

TRAIN_LEN = 150

file_prefix = 'e:/CYQ/zj_well-log-cascaded/data/A{}.csv'

INDIVIDUAL_NORMALIZATION = True

# read file and change the head name
def read_file(path):
    df = pd.read_csv(path)
    df.columns = HEAD
    return df


# make dataset using moving window with the step of -> window_step
def make_dataset(data, window_size):
    i = 0
    while i + window_size - 1 < len(data):
        yield data[i:i+window_size]
        i += 30 # set windows step here


def normalize(x):
    scaler = preprocessing.StandardScaler().fit(x)
    return scaler.transform(x), scaler


class WelllogDataset(torch.utils.data.Dataset):
    # scaler = None # the output scaler
    dataset_scaler = {} # save all scaler

    def __init__(self, input_dim, output_dim, train_id):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.train_id = train_id
        self.data_all = [] # save all the well log data
        # add all well log data
        for i in range(WELL):
            # the test and train data will be the unnormalized data
            filename = file_prefix.format(i+1)
            df = read_file(filename)
            df['DEPT'] = np.arange(1, len(df)+1)
            self.data_all.append(df)
            
        # combine all well log data
        self.dataset = pd.concat(self.data_all, axis=0, ignore_index=True)
        # save scaler
        for feature in COLUMNS:
            self.dataset_scaler[feature] = preprocessing.StandardScaler().fit(self.dataset[feature].values.reshape(-1, 1))
        self.target_scaler = preprocessing.StandardScaler().fit(self.dataset[COLUMNS_TARGET].values)
        # get train dataset
        self.input_data, self.target_data = self.train_dataset()
        self.line_num = len(self.input_data)
    # reset train dataset
    def reset_dataset(self, input_dim, output_dim):
        self.input_dim, self.output_dim = input_dim, output_dim
        self.input_data, self.target_data = self.train_dataset()
        self.line_num = len(self.input_data)
    # Returen input and target as numpy array
    def train_dataset(self):
        input_data = []
        target_data = []
        for items in self.train_id:
            data = self.data_all[items-1]
            input_ = np.array(list(make_dataset(
                normalize(data[COLUMNS[:self.input_dim]].values)[0], TRAIN_LEN)))
            if INDIVIDUAL_NORMALIZATION:
                target_ = np.array(list(make_dataset(
                    normalize(data[COLUMNS[self.input_dim:self.input_dim+self.output_dim]].values)[0], TRAIN_LEN)))
            else:
                target_ = []
                for feature in COLUMNS[self.input_dim:self.input_dim+self.output_dim]:
                    target_.append(self.dataset_scaler[feature].transform(data[feature].values.reshape(-1, 1)))
                target_ = np.concatenate(target_, axis=1)
                target_ = np.array(list(make_dataset(target_, TRAIN_LEN)))
            input_data.append(input_)
            target_data.append(target_)
        # concat all data
        return torch.from_numpy(np.concatenate(input_data)).float(), torch.from_numpy(np.concatenate(target_data)).float()

    def test_dataset(self, index):
        data = self.data_all[index-1]
        # input data
        input_ = normalize(data[COLUMNS[:-len(COLUMNS_TARGET)]].values)[0]
        if INDIVIDUAL_NORMALIZATION:
            target_, self.target_scaler = normalize(data[COLUMNS_TARGET].values)
        else:
            target_ = self.target_scaler.transform(data[COLUMNS_TARGET].values)
        return input_, target_

    def inverse_normalize(self, x):
        # this feature is only used for inverse normalization of target
        return self.target_scaler.inverse_transform(x)

    def __getitem__(self, index):
        return self.input_data[index], self.target_data[index]
    
    def __len__(self):
        return self.line_num
