import sys

import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import wandb
from wandb.keras import WandbCallback

from ffm_mlp import FourierMLP
from metrics import PSNR
from image_regression_data import train_dataset, test_dataset

# pylint: disable=no-value-for-parameter, unexpected-keyword-arg, arguments-differ
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-ancestors

OUTPUT_IMG_PREFIX = "output_g"

# Setting the hyperparemeter defaults
hyperparameter_defaults = dict(
    num_layers=10, 
    num_units=128, 
    num_units_final=3,
    gaussian=False, 
    staddev=5,
    num_units_FFM=128,
    learning_rate=1e-3,
    epochs = 100,
    beta_1 = 0.9,
    beta_2 = 0.999,
    epsilon = 1e-8
)

# Initialize wandb
wandb.init(config=hyperparameter_defaults, project="fourier-feature-dnn")
config = wandb.config

def get_model(gaussian = False):
    """Constructs a Fourier MLP model for 2D image regression
    with default arguments
    """

    config.update({'gaussian' : gaussian}, allow_val_change=True)
    model = FourierMLP(config.num_layers, config.num_units, config.num_units_final,
                       gaussian=config.gaussian, staddev=config.staddev, num_units_FFM=config.num_units_FFM)

    loss_fn = tf.keras.losses.MeanSquaredError()

    model.compile(optimizer=tf.keras.optimizers.Adam(
        learning_rate=config.learning_rate, beta_1=config.beta_1, beta_2=config.beta_2, epsilon=config.epsilon),
                  loss=loss_fn,
                  metrics=['accuracy', PSNR()])

    return model


def test_model(model, image_index, show_output=True, save_output=False):
    """Tests model on image given by image_index and returns the train and test PSNR values
    Output images are shown in matplotlib window if show_output is True and save_output is False
    Output images are saved to disk if show_output is True and save_output is True
    """
    train_X = train_dataset[0][image_index]
    train_Y = train_dataset[1][image_index]
    train_pred = model(train_X)
    psnr_train = tf.image.psnr(train_Y, train_pred, 1.0)

    test_X = test_dataset[0][image_index]
    test_Y = test_dataset[1][image_index]
    test_pred = model(test_X)
    psnr_test = tf.image.psnr(test_Y, test_pred, 1.0)


    if show_output:
        plt.imshow(train_pred)
        if save_output:
            plt.savefig(f"{OUTPUT_IMG_PREFIX}_{image_index}_train.png")
            print(f"Image saved as {OUTPUT_IMG_PREFIX}_{image_index}_train.png")
        else:
            plt.show()
        print(f"train PSNR: {psnr_train}")

        plt.imshow(test_pred)
        if save_output:
            plt.savefig(f"{OUTPUT_IMG_PREFIX}_{image_index}_test.png")
            print(f"Image saved as {OUTPUT_IMG_PREFIX}_{image_index}_test.png")
        else:
            plt.show()
        print(f"test PSNR: {psnr_test}")

    wandb.log({
        'Train PSNR Value' : psnr_train,
        'Test PSNR Value' : psnr_test
    })
    return psnr_train, psnr_test

def train_model(model, image_index, epochs, verbose=2):
    """Trains the model on 2D image dataset, but only on image with index
    image_index and for given number of epochs. The output is shown if show_output is True.
    """
    train_X = train_dataset[0][image_index]
    train_Y = train_dataset[1][image_index]

    test_X = test_dataset[0][image_index]
    test_Y = test_dataset[1][image_index]
    config.update({'epochs' : epochs}, allow_val_change=True)

    model.fit(train_X, train_Y, epochs=config.epochs, verbose=verbose, validation_data=(test_X, test_Y), callbacks=[WandbCallback()])

def find_best_stddev(start=1, end=20, epochs=100, images=16):
    """Trains multiple GaussianFFM based FourierMLPs to find the best stddev value
    from the range [start, end]. Models are trained for given number of epochs and for given
    number of images from the dataset
    """
    scores = []
    for stddev in range(start, end+1):
        image_scores = []
        for i in tqdm(range(images), desc=f"STD {stddev}: "):
            model = get_model(staddev=stddev, gaussian=True)
            train_model(model, i, epochs, verbose=0)
            _, psnr_test = test_model(model, i, show_output=False)
            image_scores.append(psnr_test)
        print(f"Average PSNR for STD {stddev} = {sum(image_scores)/len(image_scores)}")
        scores.append(image_scores)
    scores = np.array(scores)
    best_index = np.argmax(np.mean(scores, axis=-1))
    return list(range(start, end+1))[best_index]

if __name__ == "__main__":
    i_model = get_model(gaussian=True)
    index = 1
    train_epochs = 100



    # # Handling CL arguments
    # if len(sys.argv) > 1:
    #     index = int(sys.argv[1])

    #     # Number of Epochs
    #     if len(sys.argv) > 2:
    #         train_epochs = int(sys.argv[2])

    # Training and testing model
    train_model(i_model, index, train_epochs)
    test_model(i_model, index)
