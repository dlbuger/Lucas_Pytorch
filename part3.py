import numpy as np
import torch
import torch.nn as tnn
import torch.nn.functional as F
import torch.optim as topti
from torchtext import data
from torchtext.vocab import GloVe
from imdb_dataloader import IMDB


device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# Class for creating the neural network.
class Network(tnn.Module):
    def __init__(self):
        super(Network, self).__init__()
        self.lstm1 = tnn.LSTM(50, 300, 1,batch_first=True)
        self.selu = tnn.SELU()
        self.dropout = tnn.Dropout(0.5)
        self.dense1 = tnn.Linear(300, 200)
        self.norm1 = tnn.BatchNorm1d(200)
        self.dense2 = tnn.Linear(200, 128)
        self.dense3 = tnn.Linear(128,64)
        self.norm2 = tnn.BatchNorm1d(64)
        self.dense4 = tnn.Linear(64,1)

    def forward(self, input, length):
        """
        DO NOT MODIFY FUNCTION SIGNATURE
        Create the forward pass through the network.
        """
        o,(h_n,h_c) = self.lstm1(input)
        x = self.selu(o[:,-1,:].view(-1,300))
        x = self.dense1(x)
        x = self.norm1(x)
        #x += (torch.randn(x.shape[1])*0.15).to(device)
        #x = self.dropout(x)
        x = self.dense2(x)
        #x = self.dropout(x)
        x = self.selu(x)
        x = self.dense3(x)
        x = self.norm2(x)
        #x = self.dropout(x)
        x = self.dense4(x)

        
        return (x).view(-1)



class PreProcessing():
    def pre(x):
        """Called after tokenization"""
        return x

    def post(batch, vocab):
        """Called after numericalization but prior to vectorization"""
        return batch

    text_field = data.Field(lower=True, include_lengths=True, batch_first=True, preprocessing=pre, postprocessing=post)


def lossFunc():
    """
    Define a loss function appropriate for the above networks that will
    add a sigmoid to the output and calculate the binary cross-entropy.
    """
    return tnn.BCELoss()



def main():
    # Use a GPU if available, as it should be faster.
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    
    # device = torch.device('cpu')
    print("Using device: " + str(device))
    torch.cuda.empty_cache()
    # Load the training dataset, and create a data loader to generate a batch.
    textField = PreProcessing.text_field
    labelField = data.Field(sequential=False)

    train, dev = IMDB.splits(textField, labelField, train="train", validation="dev")

    textField.build_vocab(train, dev, vectors=GloVe(name="6B", dim=50))
    labelField.build_vocab(train, dev)

    trainLoader, testLoader = data.BucketIterator.splits((train, dev), shuffle=True, batch_size=64,
                                                         sort_key=lambda x: len(x.text), sort_within_batch=True)

    net = Network().to(device)
    criterion =lossFunc()
    optimiser = topti.Adam(net.parameters(), lr=0.001)  # Minimise the loss using the Adam algorithm.
    # scheduler = torch.optim.lr_scheduler.StepLR(optimiser,step_size=6, gamma=0.7)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser,10)
    for epoch in range(30):
        running_loss = 0

        for i, batch in enumerate(trainLoader):

            # Get a batch and potentially send it to GPU memory.
            inputs, length, labels = textField.vocab.vectors[batch.text[0]].to(device), batch.text[1].to(
                device), batch.label.type(torch.FloatTensor).to(device)

            labels -= 1

            
            # inputs += (torch.randn(inputs.shape[1],inputs.shape[2])*0.1).to(device)
            # if epoch >= 6:
            #     inputs += (torch.randn(inputs.shape[1],inputs.shape[2])*0.1).to(device)

            # PyTorch calculates gradients by accumulating contributions to them (useful for
            # RNNs).  Hence we must manually set them to zero before calculating them.
            optimiser.zero_grad()

            # Forward pass through the network.
            output = torch.sigmoid(net(inputs, length))

            loss = criterion(output, labels)

            # Calculate gradients.
            loss.backward()

            # Minimise the loss according to the gradient.
            optimiser.step()

            running_loss += loss.item()

            if i % 32 == 31:
                print("Epoch: %2d, Batch: %4d, Loss: %.3f" % (epoch + 1, i + 1, running_loss / 32))
                running_loss = 0
        scheduler.step()
    num_correct = 0

    # Save mode
    torch.save(net.state_dict(), "./model.pth")
    print("Saved model")

    # Evaluate network on the test dataset.  We aren't calculating gradients, so disable autograd to speed up
    # computations and reduce memory usage.
    with torch.no_grad():
        for batch in testLoader:
            # Get a batch and potentially send it to GPU memory.
            inputs, length, labels = textField.vocab.vectors[batch.text[0]].to(device), batch.text[1].to(
                device), batch.label.type(torch.FloatTensor).to(device)

            labels -= 1

            # Get predictions
            outputs = torch.sigmoid(net(inputs, length))
            predicted = torch.round(outputs)

            num_correct += torch.sum(labels == predicted).item()

    accuracy = 100 * num_correct / len(dev)

    print(f"Classification accuracy: {accuracy}")

if __name__ == '__main__':
    main()