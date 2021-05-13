import unittest
import numpy as np
import h5py
from sklearn.metrics import mean_absolute_error

from adaptiveleak.utils import message
from adaptiveleak.utils.data_utils import pad_to_length, create_groups


class TestByte(unittest.TestCase):

    def test_encode_decode_six(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        precision = 6
        width = 8
        seq_length = 8
        collected_indices = [0, 3]

        encoded = message.encode_standard_measurements(measurements=measurements,
                                                       precision=precision,
                                                       width=width,
                                                       collected_indices=collected_indices,
                                                       seq_length=seq_length,
                                                       should_compress=False)

        recovered, indices, _ = message.decode_standard_measurements(byte_str=encoded,
                                                                     num_features=measurements.shape[1],
                                                                     seq_length=seq_length,
                                                                     width=width,
                                                                     precision=precision,
                                                                     should_compress=False)

        # Check recovered values
        self.assertTrue(np.all(np.isclose(measurements, recovered)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_two(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        precision = 2
        width = 4
        seq_length = 8
        collected_indices = [0, 4]

        encoded = message.encode_standard_measurements(measurements=measurements,
                                                       precision=precision,
                                                       width=width,
                                                       collected_indices=collected_indices,
                                                       seq_length=seq_length,
                                                       should_compress=False)

        recovered, indices, _ = message.decode_standard_measurements(byte_str=encoded,
                                                                     num_features=measurements.shape[1],
                                                                     seq_length=seq_length,
                                                                     width=width,
                                                                     precision=precision,
                                                                     should_compress=False)

        expected = np.array([[0.25, 0.0, 0.75], [0.0, 0.5, -0.5]])

        # Check recovered values
        self.assertTrue(np.all(np.isclose(expected, recovered)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_ten(self):
        measurements = np.array([[0.25, -0.125, (1.0 / 512.0)], [-0.125, 0.625, -0.5]])
        precision = 10
        width = 13
        seq_length = 8
        collected_indices = [0, 6]

        encoded = message.encode_standard_measurements(measurements=measurements,
                                                       precision=precision,
                                                       width=width,
                                                       collected_indices=collected_indices,
                                                       seq_length=seq_length,
                                                       should_compress=False)

        recovered, indices, _ = message.decode_standard_measurements(byte_str=encoded,
                                                                     num_features=measurements.shape[1],
                                                                     seq_length=seq_length,
                                                                     width=width,
                                                                     precision=precision,
                                                                     should_compress=False)

        # Check recovered values
        self.assertTrue(np.all(np.isclose(measurements, recovered)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_two_compressed(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        precision = 2
        width = 4
        seq_length = 8
        collected_indices = [0, 4]

        encoded = message.encode_standard_measurements(measurements=measurements,
                                                       precision=precision,
                                                       width=width,
                                                       collected_indices=collected_indices,
                                                       seq_length=seq_length,
                                                       should_compress=True)

        recovered, indices, _ = message.decode_standard_measurements(byte_str=encoded,
                                                                     num_features=measurements.shape[1],
                                                                     seq_length=seq_length,
                                                                     width=width,
                                                                     precision=precision,
                                                                     should_compress=True)

        expected = np.array([[0.25, 0.0, 0.75], [0.0, 0.5, -0.5]])

        # Check recovered values
        self.assertTrue(np.all(np.isclose(expected, recovered)))

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_six_compressed(self):
        measurements = np.array([[1.25, -0.125, -0.75], [1.125, -0.625, -0.5]])
        precision = 4
        width = 6
        seq_length = 8
        collected_indices = [0, 4]

        encoded = message.encode_standard_measurements(measurements=measurements,
                                                       precision=precision,
                                                       width=width,
                                                       collected_indices=collected_indices,
                                                       seq_length=seq_length,
                                                       should_compress=True)

        recovered, indices, _ = message.decode_standard_measurements(byte_str=encoded,
                                                                     num_features=measurements.shape[1],
                                                                     seq_length=seq_length,
                                                                     width=width,
                                                                     precision=precision,
                                                                     should_compress=True)

        # Check recovered values
        self.assertTrue(np.all(np.isclose(measurements, recovered)))

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
        group_size = 3
        max_group_size = 4

        encoded = message.encode_grouped_measurements(measurements=measurements,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=encoded,
                                                                  seq_length=seq_length,
                                                                  num_features=measurements.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)

        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.1)

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
        group_size = 3
        max_group_size = 4

        encoded = message.encode_grouped_measurements(measurements=measurements,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=encoded,
                                                                  seq_length=seq_length,
                                                                  num_features=measurements.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)


        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.022)

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_two_groups_truncated_signed(self):
        measurements = np.array([[0.25, -0.125, -0.75], [0.125, -0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 5]
        widths = [6, 4]
        group_size = 3
        max_group_size = 4

        encoded = message.encode_grouped_measurements(measurements=measurements,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=encoded,
                                                                  seq_length=seq_length,
                                                                  num_features=measurements.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)


        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.002)

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
        group_size = 2
        max_group_size = 2

        encoded = message.encode_grouped_measurements(measurements=measurements,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=encoded,
                                                                  seq_length=seq_length,
                                                                  num_features=measurements.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)

        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.012)

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
        group_size = 2
        max_group_size = 2

        encoded = message.encode_grouped_measurements(measurements=measurements,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        padded = pad_to_length(encoded, length=len(encoded) + 6)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=padded,
                                                                  seq_length=seq_length,
                                                                  num_features=measurements.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)

        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.012)

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
        group_size = 100
        max_group_size = 125

        encoded = message.encode_grouped_measurements(measurements=inputs,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=encoded,
                                                                  seq_length=seq_length,
                                                                  num_features=inputs.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)

        error = mean_absolute_error(y_true=inputs, y_pred=decoded)
        self.assertLessEqual(error, 0.01)

    def test_encode_decode_large_two(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][495]  # [50, 6]

        widths = [9, 8, 8]
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2
        group_size = 100
        max_group_size = 125

        encoded = message.encode_grouped_measurements(measurements=inputs,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=encoded,
                                                                  seq_length=seq_length,
                                                                  num_features=inputs.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)

        error = np.average(np.sum(np.square(decoded - inputs), axis=-1))
        self.assertLessEqual(error, 0.01)

    def test_encode_decode_large_group(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][495]  # [50, 6]

        widths = [9, 8]
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2
        group_size = 150
        max_group_size = 200

        encoded = message.encode_grouped_measurements(measurements=inputs,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=encoded,
                                                                  seq_length=seq_length,
                                                                  num_features=inputs.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)

        error = mean_absolute_error(y_true=inputs, y_pred=decoded)
        self.assertLessEqual(error, 0.01)

    def test_encode_decode_large_tight(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][495]  # [50, 6]

        widths = [4, 4]
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2
        group_size = 150
        max_group_size = 200

        groups = create_groups(inputs, max_num_groups=10, max_group_size=200)

        encoded = message.encode_grouped_measurements(measurements=inputs,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=encoded,
                                                                  seq_length=seq_length,
                                                                  num_features=inputs.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)

        error = mean_absolute_error(y_true=inputs, y_pred=decoded)

        print(error)

        self.assertLessEqual(error, 0.1)

    def test_encode_decode_large_padded(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][0]  # [50, 6]

        widths = [9, 8, 8]
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2
        group_size = 100
        max_group_size = 125

        encoded = message.encode_grouped_measurements(measurements=inputs,
                                                      collected_indices=collected_indices,
                                                      seq_length=seq_length,
                                                      widths=widths,
                                                      non_fractional=non_fractional,
                                                      group_size=group_size)

        padded = pad_to_length(encoded, len(encoded) + 6)

        decoded, indices, _ = message.decode_grouped_measurements(encoded=padded,
                                                                  seq_length=seq_length,
                                                                  num_features=inputs.shape[1],
                                                                  non_fractional=non_fractional,
                                                                  max_group_size=max_group_size)

        error = mean_absolute_error(y_true=inputs, y_pred=decoded)
        self.assertLessEqual(error, 0.01)


class TestGroupWidths(unittest.TestCase):

    def test_encode_decode_widths(self):
        widths = [31, 1, 9, 12]
        shifts = [3, -4, 0, 2] 

        encoded = message.encode_group_widths(widths=widths, shifts=shifts)
        rec_widths, rec_shifts = message.decode_group_widths(encoded=encoded)

        self.assertEqual(rec_widths, widths)
        self.assertEqual(rec_shifts, shifts)

    def test_encode_decode_overflow(self):
        widths = [32, 4, 6]
        shifts = [1, 4, -5]

        encoded = message.encode_group_widths(widths=widths, shifts=shifts)
        rec_widths, rec_shifts = message.decode_group_widths(encoded=encoded)

        self.assertEqual(rec_widths, [31, 4, 6])
        self.assertEqual(rec_shifts, [1, 3, -4])


class TestStable(unittest.TestCase):

    def test_encode_decode_two_groups(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 1]
        width = 5

        encoded = message.encode_stable_measurements(measurements=measurements,
                                                     collected_indices=collected_indices,
                                                     seq_length=seq_length,
                                                     width=width,
                                                     non_fractional=non_fractional)

        decoded, indices, widths = message.decode_stable_measurements(encoded=encoded,
                                                                      seq_length=seq_length,
                                                                      num_features=measurements.shape[1],
                                                                      non_fractional=non_fractional)

        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.1)

        # Check the returned width
        self.assertEqual(len(widths), 1)
        self.assertEqual(widths[0], 5)

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_two_groups_truncated(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 5]
        width = 4

        encoded = message.encode_stable_measurements(measurements=measurements,
                                                     collected_indices=collected_indices,
                                                     seq_length=seq_length,
                                                     width=width,
                                                     non_fractional=non_fractional)

        decoded, indices, widths = message.decode_stable_measurements(encoded=encoded,
                                                                      seq_length=seq_length,
                                                                      num_features=measurements.shape[1],
                                                                      non_fractional=non_fractional)

        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.03)

        # Check the widths
        self.assertEqual(len(widths), 1)
        self.assertEqual(widths[0], 4)

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_two_groups_truncated_signed(self):
        measurements = np.array([[0.25, -0.125, -0.75], [0.125, -0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 5]
        width = 4

        encoded = message.encode_stable_measurements(measurements=measurements,
                                                     collected_indices=collected_indices,
                                                     seq_length=seq_length,
                                                     width=width,
                                                     non_fractional=non_fractional)

        decoded, indices, widths = message.decode_stable_measurements(encoded=encoded,
                                                                      seq_length=seq_length,
                                                                      num_features=measurements.shape[1],
                                                                      non_fractional=non_fractional)

        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.002)

        # Check the width
        self.assertEqual(len(widths), 1)
        self.assertEqual(widths[0], 4)

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_three_groups(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 7]
        width = 5

        encoded = message.encode_stable_measurements(measurements=measurements,
                                                     collected_indices=collected_indices,
                                                     seq_length=seq_length,
                                                     width=width,
                                                     non_fractional=non_fractional)

        decoded, indices, widths = message.decode_stable_measurements(encoded=encoded,
                                                                      seq_length=seq_length,
                                                                      num_features=measurements.shape[1],
                                                                      non_fractional=non_fractional)

        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.012)

        # Check widths
        self.assertEqual(len(widths), 1)
        self.assertEqual(widths[0], 5)

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_padded(self):
        measurements = np.array([[0.25, -0.125, 0.75], [-0.125, 0.625, -0.5]])
        non_fractional = 2
        seq_length = 8
        collected_indices = [0, 7]
        width = 5

        encoded = message.encode_stable_measurements(measurements=measurements,
                                                     collected_indices=collected_indices,
                                                     seq_length=seq_length,
                                                     width=width,
                                                     non_fractional=non_fractional)

        padded = pad_to_length(encoded, length=len(encoded) + 6)

        decoded, indices, widths = message.decode_stable_measurements(encoded=padded,
                                                                      seq_length=seq_length,
                                                                      num_features=measurements.shape[1],
                                                                      non_fractional=non_fractional)

        # Check recovered values
        error = mean_absolute_error(y_true=measurements, y_pred=decoded)
        self.assertLess(error, 0.012)

        # Check widths
        self.assertEqual(len(widths), 1)
        self.assertEqual(widths[0], 5)

        # Check indices
        self.assertEqual(len(indices), 2)
        self.assertEqual(indices[0], collected_indices[0])
        self.assertEqual(indices[1], collected_indices[1])

    def test_encode_decode_large(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][0]  # [50, 6]

        width = 8
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2

        encoded = message.encode_stable_measurements(measurements=inputs,
                                                     collected_indices=collected_indices,
                                                     seq_length=seq_length,
                                                     width=width,
                                                     non_fractional=non_fractional)

        decoded, indices, _ = message.decode_stable_measurements(encoded=encoded,
                                                                 seq_length=seq_length,
                                                                 num_features=inputs.shape[1],
                                                                 non_fractional=non_fractional)

        error = mean_absolute_error(y_true=inputs, y_pred=decoded)
        self.assertLessEqual(error, 0.01)

    def test_encode_decode_large_two(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][495]  # [50, 6]

        width = 8
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2

        encoded = message.encode_stable_measurements(measurements=inputs,
                                                     collected_indices=collected_indices,
                                                     seq_length=seq_length,
                                                     width=width,
                                                     non_fractional=non_fractional)

        decoded, indices, _ = message.decode_stable_measurements(encoded=encoded,
                                                                 seq_length=seq_length,
                                                                 num_features=inputs.shape[1],
                                                                 non_fractional=non_fractional)

        error = mean_absolute_error(y_true=inputs, y_pred=decoded)
        self.assertLessEqual(error, 0.01)

    def test_encode_decode_large_tight(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][495]  # [50, 6]

        width = 4
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2

        encoded = message.encode_stable_measurements(measurements=inputs,
                                                     collected_indices=collected_indices,
                                                     seq_length=seq_length,
                                                     width=width,
                                                     non_fractional=non_fractional)

        decoded, indices, _ = message.decode_stable_measurements(encoded=encoded,
                                                                 seq_length=seq_length,
                                                                 num_features=inputs.shape[1],
                                                                 non_fractional=non_fractional)

        error = mean_absolute_error(y_true=inputs, y_pred=decoded)
        self.assertLessEqual(error, 0.065)

    def test_encode_decode_large_padded(self):
        # Load the data
        with h5py.File('../../datasets/uci_har/train/data.h5', 'r') as fin:
            inputs = fin['inputs'][495]  # [50, 6]

        width = 8
        seq_length = inputs.shape[0]
        collected_indices = list(range(seq_length))
        non_fractional = 2

        encoded = message.encode_stable_measurements(measurements=inputs,
                                                     collected_indices=collected_indices,
                                                     seq_length=seq_length,
                                                     width=width,
                                                     non_fractional=non_fractional)
        
        encoded = pad_to_length(encoded, len(encoded) + 10)

        decoded, indices, _ = message.decode_stable_measurements(encoded=encoded,
                                                                 seq_length=seq_length,
                                                                 num_features=inputs.shape[1],
                                                                 non_fractional=non_fractional)

        error = mean_absolute_error(y_true=inputs, y_pred=decoded)
        self.assertLessEqual(error, 0.01)


class TestDeltaEncode(unittest.TestCase):

    def test_encode(self):
        measurements = np.array([[10.0, 10.0], [12.0, 12.0], [12.5, 11.5]])
        
        encoded = message.delta_encode(measurements)
        expected = np.array([[10.0, 10.0], [2.0, 2.0], [0.5, -0.5]]) 

        self.assertTrue(np.all(np.isclose(encoded, expected)))

    def test_decode(self):
        encoded = np.array([[10.0, 10.0], [2.0, 2.0], [0.5, -0.5]]) 
        recovered = message.delta_decode(encoded)

        expected = np.array([[10.0, 10.0], [12.0, 12.0], [12.5, 11.5]])

        self.assertTrue(np.all(np.isclose(recovered, expected)))

    def test_single_feature(self):
        rand = np.random.RandomState(seed=3489)
        seq_length = 7

        measurements = rand.uniform(low=-2.0, high=2.0, size=(seq_length, 1))

        encoded = message.delta_encode(measurements)
        recovered = message.delta_decode(encoded)

        self.assertTrue(np.all(np.isclose(recovered, measurements)))

    def test_many_features(self):
        rand = np.random.RandomState(seed=3489)
        seq_length = 12
        num_features = 5

        measurements = rand.uniform(low=-2.0, high=2.0, size=(seq_length, num_features))

        encoded = message.delta_encode(measurements)
        recovered = message.delta_decode(encoded)

        self.assertTrue(np.all(np.isclose(recovered, measurements)))


if __name__ == '__main__':
    unittest.main()
