import os
import random
import argparse
import torch
import torch.nn as nn
import numpy as np
from torch.utils.data import DataLoader
from tqdm import tqdm
from model import *
from Loss import *
from data_load import *
from model_evaluation import *

num_epochs = 60



n_lang = 3
model = BLSTM_E2E_LID(n_lang=n_lang,
                      dropout=0.25,
                      input_dim=437,
                      hidden_size=256,
                      num_emb_layer=2,
                      num_lstm_layer=3,
                      emb_dim=256)

device = torch.device('cuda:2' if torch.cuda.is_available() else 'cpu')
# model = nn.DataParallel(model, device_ids=[0, 1, 2, 3])
model.to(device)

# train_txt = '/home/hexin/Desktop/hexin/datasets/First_workshop_codeswitching/' \
#             'PartB_Telugu/PartB_Telugu/Train/utt2lan.txt'
# train_txt = '/home/hexin/Desktop/hexin/datasets/First_workshop_codeswitching/' \
#             'PartB_Tamil/PartB_Tamil/Train/utt2lan.txt'
train_txt = '/home/hexin/Desktop/hexin/datasets/First_workshop_codeswitching/' \
            'PartB_Gujarati/PartB_Gujarati//Train/utt2lan.txt'
train_set = RawFeatures(train_txt)

# valid_txt = '/home/hexin/Desktop/hexin/datasets/First_workshop_codeswitching/' \
#             'PartB_Telugu/PartB_Telugu/Dev/utt2lan.txt'
# valid_txt = '/home/hexin/Desktop/hexin/datasets/First_workshop_codeswitching/' \
#             'PartB_Tamil/PartB_Tamil/Dev/utt2lan.txt'
valid_txt = '/home/hexin/Desktop/hexin/datasets/First_workshop_codeswitching/' \
            'PartB_Gujarati/PartB_Gujarati/Dev/utt2lan.txt'
valid_set = RawFeatures(valid_txt)

batch_size = 8
train_data = DataLoader(dataset=train_set,
                        batch_size=batch_size,
                        pin_memory=True,
                        num_workers=16,
                        shuffle=True,
                        collate_fn=collate_fn)

valid_data = DataLoader(dataset=valid_set,
                        batch_size=1,
                        pin_memory=True,
                        # num_workers=16,
                        shuffle=False,
                        collate_fn=collate_fn)

# loss_func_PIT = PermutationInvariantLoss(device=device).to(device)
loss_func_DCL = DeepClusteringLoss().to(device)
loss_func_CRE = nn.CrossEntropyLoss().to(device)

optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
T_max = num_epochs
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=T_max)

# Train the model
total_step = len(train_data)
# training_loss = []
# validation_loss = []
best_acc = 0

for epoch in tqdm(range(num_epochs)):
    loss_item = 0
    model.train()
    for step, (utt, labels, seq_len) in enumerate(train_data):
        utt_ = utt.to(device=device, dtype=torch.float)
        utt_ = rnn_utils.pack_padded_sequence(utt_, seq_len, batch_first=True)
        # labels = labels.to(device=device,dtype=torch.long)
        # labels_ = labels.reshape(-1)
        labels_ = rnn_util.pack_padded_sequence(labels, seq_len,batch_first=True).data.to(device)

        # Forward pass\
        outputs, embeddings = model(utt_)
        # embeddings, outputs = model(utt_)  # output <=> prerdict_train
        loss_DCL = loss_func_DCL(embeddings, labels_)
        loss_CRE = loss_func_CRE(outputs, labels_)
        loss = 0.7 * loss_CRE + 0.3 * loss_DCL

        # Backward and optimize
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        scheduler.step()
        if step % 200 == 0:
            print("Epoch [{}/{}], Step [{}/{}] Loss: {:.4f} CRE: {:.4f} DCL: {:.4f}"
                  .format(epoch + 1, num_epochs, step + 1, total_step, loss.item(), loss_CRE.item(), loss_DCL.item()))
    torch.save(model.state_dict(), '/home/hexin/Desktop/models/' + '{}.ckpt'.format('Tamil_BLSTM_EEND'))
    model.eval()
    correct = 0
    total = 0
    predicts = []
    FAR_list = torch.zeros(n_lang)
    FRR_list = torch.zeros(n_lang)
    eer = 0
    for step, (utt, labels, seq_len) in enumerate(valid_data):
        utt = utt.to(device=device, dtype=torch.float)
        utt_ = rnn_utils.pack_padded_sequence(utt, seq_len, batch_first=True)
        labels_ = rnn_util.pack_padded_sequence(labels, seq_len, batch_first=True).data.to(device)
        # Forward pass\
        outputs, embeddings = model(utt_)
        predicted = torch.argmax(outputs,-1)
        total += labels.size(-1)
        correct += (predicted == labels_).sum().item()
        FAR, FRR = compute_far_frr(n_lang, predicted, labels_)
        FAR_list += FAR
        FRR_list += FRR
    acc = correct/total
    print('Current Acc.: {:.4f} %'.format(100 * acc))
    for i in range(n_lang):
        eer_ = (FAR_list[i]/total + FRR_list[i]/total)/2
        eer += eer_
        print("EER for label {}: {:.4f}%".format(i, eer_*100))
    print('EER: {:.4f} %'.format(100*eer/n_lang))
# print('Val Loss: {:.4f}'.format(loss_test.item()))
