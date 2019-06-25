#!/usr/bin/env python3
import json
import pretty_midi
import scipy.io
from utils import io
from copy import copy
import tarfile
import sys
import os
import csv


# The dictionary prototype for containing the ground-truth
gt = {
    "precise-alignment": {
        "onsets": [],
        "offsets": []
    },
    "non-aligned": {
        "onsets": [],
        "offsets": []
    },
    "velocities": [],
    "notes": [],
    "pitches": [],
    "f0": [],
}


def change_ext(input_fn, new_ext):
    """
    Return the input path `input_fn` with `new_ext` as extension
    """

    root = input_fn[ :input_fn.rfind('-')]
    if not new_ext.startswith('.'):
        new_ext = '.' + new_ext

    return root + new_ext


def from_midi(midi_fn, alignment='precise-alignment', pitches=True, velocities=True, merge=True):
    """
    Open a midi file `midi_fn` and convert it to our ground-truth
    representation. This fills velocities, pitches and alignment (default:
    `precise-alignment`). Returns a list containing a dictionary. `alignment`
    can also be `None` or `False`, in that case no alignment is filled. If `merge` is
    True, the returned list will contain a dictionary for each track.
    """
    new_midi_fn = change_ext(midi_fn, '.mid')
    if not os.path.exists(new_midi_fn):
        new_midi_fn = change_ext(midi_fn, '.midi')

    midi_tracks = io.open_midi(new_midi_fn, merge=merge)

    out = list()

    if merge:
        midi_tracks = [midi_tracks]

    for track in midi_tracks:
        data = copy(gt)

        if alignment:
            onsets, offsets = data[alignment].values()
            alignment = True
        else:
            alignment = False

        for note_group in track:
            for note in note_group:
                if pitches:
                    data["pitches"].append(note.pitch)
                if velocities:
                    data["velocities"].append(note.velocity)
                if alignment:
                    onsets.append(float(note.start))
                    offsets.append(float(note.end))
        out.append(data)

    return out


def from_phenicx_txt(txt_fn, non_aligned=False):
    """
    Open a txt file `txt_fn` in the PHENICX format and convert it to our
    ground-truth representation. This fills: `precise-alignment`.
    """
    out_list = list()
    txt_fn = change_ext(txt_fn, 'txt')

    with open(txt_fn) as f:
        lines = f.readlines()

    out = copy(gt)
    for line in lines:
        fields = line.split(',')
        out["notes"].append(fields[2])
        out["precise-alignment"]["onsets"].append(float(fields[0]))
        out["precise-alignment"]["offsets"].append(float(fields[1]))
    out_list.append(out)

    return out_list


def from_bach10_txt(txt_fn, sources=range(4)):
    """
    Open a txt file `txt_fn` in the MIREX format (Bach10) and convert it to
    our ground-truth representation. This fills: `precise-alignment`, `pitches`.
    `sources` is an iterable containing the indices of the  sources to be
    considered, where the first source is 0. Returns a list of dictionary, one
    per source.
    """
    out_list = list()
    txt_fn = change_ext(txt_fn, 'txt')

    with open(txt_fn) as f:
        lines = f.readlines()

    for source in sources:
        out = copy(gt)
        for line in lines:
            fields = line.split(' ')
            if int(fields[-1] - 1) == source:
                out["pitches"].append(int(fields[2]))
                out["precise-alignment"]["onsets"].append(float(fields[0]) / 1000.)
                out["precise-alignment"]["offsets"].append(float(fields[1]) / 1000.)
        out_list.append(out)

    return out_list


def from_bach10_f0(nmat_fn, sources=range(4)):
    """
    Open a matlab mat file `nmat_fn` in the MIREX format (Bach10) for frame
    evaluation and convert it to our ground-truth representation. This fills:
    `f0`.  `sources` is an iterable containing the indices of the  sources to
    be considered, where the first source is 0.  Returns a list of dictionary,
    one per source.
    """
    out_list = list()
    nmat_fn = change_ext(nmat_fn, '.mat')

    f0s = scipy.io.loadmat(nmat_fn)['GTF0s']
    for source in sources:
        out = copy('gt')
        out["f0"] = float(f0s[source])
        out_list.append(out)

    return out_list


def from_musicnet_csv(csv_fn, fr=44100.0):
    """
    Open a csv file `csv_fn` and convert it to our ground-truth representation.
    This fills: `precise-alignment`, `non-aligned`, `pitches`.
    This returns a list containing only one dict. `fr` is the framerate of the
    audio files (MusicNet csv contains the frame number as onset and offsets of
    each note) and it shold be a float.

    N.B. MusicNet contains wav files at 44100 Hz as framerate.
    """
    csv_fn = change_ext(csv_fn, 'csv')
    data = csv.reader(open(csv_fn), delimiter=',')
    out = copy(gt)

    # skipping first line
    next(data)

    for row in data:
        # converting everything to float, except the last onw that is the
        # duration name as string
        row = list(map(float, row[:-1]))

        out["precise-alignment"]["onsets"].append((row[0]) / fr)
        out["precise-alignment"]["offsets"].append(row[1] / fr)
        out["pitches"].append(int(row[3]))
        out["non-aligned"]["onsets"].append(row[4])
        out["non-aligned"]["offsets"].append(row[4] + row[5])

    return [out]


def merge(*args):
    """
    Merges lists of dictionaries, by adding each other the values of
    corresponding dictionaries
    """

    assert all(type(x) is list for x in args), "Input types must be lists"

    assert all(len(x) == len(args[0]) for x in args[1:]), "Cannot merge list with different lenghts"

    if len(args) == 1:
        return args[0]

    obj1_copy = copy(args[0])
    for i, d1 in enumerate(obj1_copy):
        for arg in args[1:]:
            d2 = arg[i]
            for key in d1.keys():
                d1_element = [d1[key]]
                if type(d1_element) is dict:
                    d1[key] = merge([d1_element], [d2[key]])[0]
                else:
                    d1_element.append(d2[key])
                d1[key] = d1_element

    return obj1_copy


func_map = {
    'Bach10': [(from_bach10_f0, {}), (from_bach10_txt, {}), (from_midi, {'alignment': 'non-aligned', 'pitches': False, 'velocities': False, 'merge': False})],
    'SMD': [(from_midi, {})],
    'PHENICX': [(from_phenicx_txt, {}), (from_midi, {'alignment': 'non-aligned'})],
    'MusicNet': [(from_musicnet_csv, {})],
    'TRIOS_dataset': [(from_midi, {})],
    'Maestro': [(from_midi, {})]
}


def create_gt(data_fn, args, xztar=False):
    """
    Parse the yaml file `data_fn` and convert all ground-truth to our
    representation. Then dump it according to the specified paths. Finally,
    if `xztar` is True, create a xztar archive called 'ground-truth.tar.xz' in
    this directory containing only the ground truth file in their final
    positions.
    """

    print("Opening JSON file: " + data_fn)

    json_file = json.load(open(data_fn, 'r'))

    to_be_included_in_the_archive = []
    for dataset in json_file['datasets']:
        if dataset['name'] in args:
            continue

        print("\n------------------------\n")
        print("Starting processing " + dataset['name'])
        for song in dataset['songs']:
            print(" elaborating " + song['title'])
            paths = song['ground-truth']

            for path in paths:
                final_path = os.path.join(json_file['install_dir'], path)
                # calling each function listed in the map and merge everything
                out = merge(*[func(final_path, **params)
                              for func, params in func_map[dataset['name']]])

                # get the index of the track from the path
                idx = path[path.rfind('-') + 1 : path.rfind('.')]
                idx = min(len(out) - 1, int(idx))

                print("   saving " + final_path)
                json.dump(out[idx], open(final_path, 'w'))

            to_be_included_in_the_archive.append(final_path)

    # creating the archive
    if xztar:
        print("\n\nCreating the final archive")
        with tarfile.open('ground-truth.tar.xz', mode='w:xz') as tf:
            for fname in to_be_included_in_the_archive:
                tf.add(fname)


if __name__ == "__main__":
    print("Usage: ")
    print("  python3 convert_gt.py [list of datasets to be excluded]")
    print()

    create_gt('datasets.json', sys.argv, xztar=True)
