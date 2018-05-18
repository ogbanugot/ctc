# !/home/anitakau/envs/tensorflow-workq/bin/python
# !/home/marith1/envs/tensorflow/bin/python

import argparse

import keras.backend as K
from keras import models

import nn_models
from DataGenerator import DataGenerator
from data import combine_all_wavs_and_trans_from_csvs
from utils import predict_batch, calc_wer


def main(args):
    args.model_load = "models/testing_pred"
    try:

        if not args.model_load:
            raise ValueError()
        audio_dir = args.audio_dir

        print "\nReading test data: "
        _, df = combine_all_wavs_and_trans_from_csvs(audio_dir)

        batch_size = args.batch_size
        batch_index = args.batch_index

        mfcc_features = args.mfccs
        n_mels = args.mels
        frequency = 16           # Sampling rate of data in khz (LibriSpeech is 16khz)

        # Training data_params:
        model_load = args.model_load
        load_multi = args.load_multi

        # Sets the full dataset in audio_dir to be available through data_generator
        # The data_generator doesn't actually load the audio files until they are requested through __get_item__()
        epoch_length = 0

        # Load trained model
        # When loading custom objects, Keras needs to know where to find them.
        # The CTC lambda is a dummy function
        custom_objects = {'clipped_relu': nn_models.clipped_relu,
                          '<lambda>': lambda y_true, y_pred: y_pred}

        # When loading a parallel model saved *while* running on GPU, use load_multi
        if load_multi:
            model = models.load_model(model_load, custom_objects=custom_objects)
            model = model.layers[-2]
            print "\nLoaded existing model: ", model_load

        # Load single GPU/CPU model or model saved *after* finished training
        else:
            model = models.load_model(model_load, custom_objects=custom_objects)
            print "\nLoaded existing model: ", model_load

        # Dummy loss-function to compile model, actual CTC loss-function defined as a lambda layer in model
        loss = {'ctc': lambda y_true, y_pred: y_pred}

        model.compile(loss=loss, optimizer='Adam')

        feature_shape = model.input_shape[0][2]

        # Model feature type
        if not args.feature_type:
            if feature_shape == 26:
                feature_type = 'mfcc'
            else:
                feature_type = 'spectrogram'
        else:
            feature_type = args.feature_type

        print "Feature type: ", feature_type

        # Data generation parameters
        data_params = {'feature_type': feature_type,
                       'batch_size': batch_size,
                       'frame_length': 20 * frequency,
                       'hop_length': 10 * frequency,
                       'mfcc_features': mfcc_features,
                       'n_mels': n_mels,
                       'epoch_length': epoch_length,
                       'shuffle': False
                       }

        # Data generators for training, validation and testing data
        data_generator = DataGenerator(df, **data_params)

        # Print model summary
        model.summary()

        # Creates a test function that takes preprocessed sound input and outputs predictions
        # Used to calculate WER while training the network
        input_data = model.get_layer('the_input').input
        y_pred = model.get_layer('ctc').input[0]
        test_func = K.function([input_data], [y_pred])

        if args.calc_wer:
            print "\n - Calculation WER on ", audio_dir
            wer = calc_wer(test_func, data_generator)
            print "Average WER: ", wer[1]

        predictions = predict_batch(data_generator, test_func, batch_index)
        print "\n - Predictions from batch index: ", batch_index, "\nFrom: ", audio_dir, "\n"
        for i in predictions:
            print "Original: ", i[0]
            print "Predicted: ", i[1], "\n"

    except (Exception, ArithmeticError) as e:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        print message

    finally:
        # Clear memory
        K.clear_session()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # Predict data params:
    parser.add_argument('--audio_dir', type=str, default="data_dir/librivox-test-clean.csv",
                        help='Path to .csv file of audio to predict')
    parser.add_argument('--batch_size', type=int, default=10,
                        help='Number of files to predict.')
    parser.add_argument('--batch_index', type=int, default=0,
                        help='Index of batch in .csv file to predict.')
    parser.add_argument('--calc_wer', type=bool, default=True,
                        help='Whether to calculate the word error rate on the data in audio_dir.')

    # Only need to specify these if feature params are changed from default
    parser.add_argument('--feature_type', type=str,
                        help='What features to extract: mfcc, spectrogram. '
                             'If none is specified it tries to detect feature type from input_shape.')

    parser.add_argument('--mfccs', type=int, default=26,
                        help='Number of mfcc features per frame to extract.')
    parser.add_argument('--mels', type=int, default=40,
                        help='Number of mels to use in feature extraction.')

    # Model load params:
    parser.add_argument('--model_load', type=str,
                        help='Path of existing model to load.')
    parser.add_argument('--load_multi', type=bool, default=False,
                        help='Load multi gpu model saved during parallel GPU training.')

    args = parser.parse_args()

    main(args)
