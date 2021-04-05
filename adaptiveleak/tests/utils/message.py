import unittest
import numpy as np
import h5py

from adaptiveleak.utils import message
from adaptiveleak.utils.data_utils import pad_to_length


class TestByte(unittest.TestCase):

    def test_encode_decode_six(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        precision = 6
        seq_length = 8
        collected_indices = [0, 3]

        encoded = message.encode_byte_measurements(measurements=measurements,
                                                   precision=precision,
                                                   collected_indices=collected_indices,
                                                   seq_length=seq_length)

        recovered, indices = message.decode_byte_measurements(byte_str=encoded,
                                                              num_features=measurements.shape[1],
                                                              seq_length=8)

        
        # Check recovered values
        self.assertTrue(np.all(np.isclose(measurements, recovered)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_two(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        precision = 2
        seq_length = 8
        collected_indices = [0, 4]

        encoded = message.encode_byte_measurements(measurements=measurements,
                                                   precision=precision,
                                                   collected_indices=collected_indices,
                                                   seq_length=seq_length)

        recovered, indices = message.decode_byte_measurements(byte_str=encoded,
                                                              num_features=measurements.shape[1],
                                                              seq_length=8)

        expected = np.array([[0.25, 0.0, 0.75], [0.0, 0.5, -0.5]])

        # Check recovered values
        self.assertTrue(np.all(np.isclose(expected, recovered)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])


class TestGroups(unittest.TestCase):

    def test_encode_decode_two_groups(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 1]
        widths = [6, 5]

        encoded = message.encode_grouped_measurements(measurements=measurements,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional)

        decoded, indices = message.decode_grouped_measurements(encoded=encoded,
                                                               seq_length=seq_length,
                                                               num_features=measurements.shape[1],
                                                               non_fractional=non_fractional)

        # Check recovered values
        self.assertTrue(np.all(np.isclose(decoded, measurements)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_two_groups_truncated(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 5]
        widths = [6, 4]

        encoded = message.encode_grouped_measurements(measurements=measurements,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional)

        decoded, indices = message.decode_grouped_measurements(encoded=encoded,
                                                               seq_length=seq_length,
                                                               num_features=measurements.shape[1],
                                                               non_fractional=non_fractional)

        expected = np.array([[0.25, -0.125, 0.75], [0.0, 0.5, -0.5]])

        # Check recovered values
        self.assertTrue(np.all(np.isclose(decoded, expected)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_three_groups(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 7]
        widths = [6, 5, 5]

        encoded = message.encode_grouped_measurements(measurements=measurements,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional)

        decoded, indices = message.decode_grouped_measurements(encoded=encoded,
                                                               seq_length=seq_length,
                                                               num_features=measurements.shape[1],
                                                               non_fractional=non_fractional)

        # Check recovered values
        self.assertTrue(np.all(np.isclose(decoded, measurements)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_padded(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 7]
        widths = [6, 5, 5]

        encoded = message.encode_grouped_measurements(measurements=measurements,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional)

        padded = pad_to_length(encoded, length=len(encoded) + 6)

        decoded, indices = message.decode_grouped_measurements(encoded=padded,
                                                               seq_length=seq_length,
                                                               num_features=measurements.shape[1],
                                                               non_fractional=non_fractional)

        # Check recovered values
        self.assertTrue(np.all(np.isclose(decoded, measurements)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_large(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][0]  # [50, 6]

        widths = [9, 8, 8]
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2

        encoded = message.encode_grouped_measurements(measurements=inputs,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional)

        decoded, indices = message.decode_grouped_measurements(encoded=encoded,
                                                               seq_length=seq_length,
                                                               num_features=inputs.shape[1],
                                                               non_fractional=non_fractional)

        error = np.average(np.sum(np.square(decoded - inputs), axis=-1))
        self.assertLessEqual(error, 0.01)

    def test_encode_decode_large_two(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][495]  # [50, 6]

        widths = [9, 8, 8]
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2

        encoded = message.encode_grouped_measurements(measurements=inputs,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional)

        decoded, indices = message.decode_grouped_measurements(encoded=encoded,
                                                               seq_length=seq_length,
                                                               num_features=inputs.shape[1],
                                                               non_fractional=non_fractional)

        error = np.average(np.sum(np.square(decoded - inputs), axis=-1))
        self.assertLessEqual(error, 0.01)

    def test_encode_decode_large_padded(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][0]  # [50, 6]

        widths = [9, 8, 8]
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2

        encoded = message.encode_grouped_measurements(measurements=inputs,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional)

        padded = pad_to_length(encoded, len(encoded) + 6)

        decoded, indices = message.decode_grouped_measurements(encoded=padded,
                                                               seq_length=seq_length,
                                                               num_features=inputs.shape[1],
                                                               non_fractional=non_fractional)

        error = np.average(np.sum(np.square(decoded - inputs), axis=-1))
        self.assertLessEqual(error, 0.01)

 
if __name__ == '__main__':
    unittest.main()

