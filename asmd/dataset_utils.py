from copy import deepcopy

import numpy as np

from . import utils


def chose_score_type(score_type, gts):
    """
    Return the proper score type according to the following rules

    Parameters
    ---

    score_type : list of str
        The key to retrieve the list of notes from the ground_truths. If
        multiple keys are provided, only one is retrieved by using the
        following criteria: if there is `precise_alignment` in the list of
        keys and in the ground truth, use that; otherwise, if there is
        `broad_alignment` in the list of keys and in the ground truth, use
        that; otherwise if `misaligned` in the list of keys and in the ground
        truth, use use `score`.

    gts : list of dict
        The list of ground truths from which you want to chose a score_type
    """
    if len(score_type) > 1:
        if 'precise_alignment' in score_type and len(
                gts[0]['precise_alignment']['pitches']) > 0:
            score_type = 'precise_alignment'
        elif 'broad_alignment' in score_type and len(
                gts[0]['broad_alignment']['pitches']) > 0:
            score_type = 'broad_alignment'
        elif 'misaligned' in score_type and len(
                gts[0]['misaligned']['pitches']) > 0:
            score_type = 'misaligned'
        else:
            score_type = 'score'

    else:
        score_type = score_type[0]
    return score_type


def filter(dataset,
           instruments=[],
           ensemble=None,
           mixed=True,
           sources=False,
           all=False,
           composer='',
           datasets=[],
           groups=[],
           ground_truth=[],
           copy=False):
    """
    Filter the paths of the songs which accomplish the filter described
    in `kwargs`. If this dataset was already fltered, only filters those
    paths that are already included.

    For advanced usage:

    So that a dataset can be filtered, it must have the following keys:

    * songs
    * name
    * included

    Optionally, the following dataset-level filters can be applied if the
    corresponding keys are present:

    * ensemble
    * ground_truth

    Similarly, each song must have the key ``included`` and optionally the
    other keys that you want to filter, as described by the arguments of
    this function.

    Arguments
    ---------
    instruments : list of str
        a list of strings representing the instruments that you
        want to select (exact match with song)
    ensemble : bool
        if loading songs which are composed for an ensemble of
        instrument. If None, ensemble field will not be checked and will
        select both (default None)
    mixed : bool
        if returning the mixed track for ensemble song
        (default  True )
    sources : bool
        if returning the source track for ensemble recording
        which provide it (default  False )
    all : bool
        only valid if  sources  is  True : if  True , all
        sources (audio and ground-truth) are returned, if
        False, only the first target instrument is returned. Default False.
    composer : string
        the surname of the composer to filter
    groups : list of strings
        a list of strings containing the name of the groups that you want
        to retrieve with a logic 'AND' among them. If empty, all groups are
        used. Example of groups are: 'train', 'validation', 'test'. The
        available groups depend on the dataset. Only Maestro dataset
        supported for now.
    datasets : list of strings
        a list of strings containing the name of the datasets to be used.
        If empty, all datasets are used. See :doc:`License` for the
        list of default datasets.
    ground_truth : dict[str, int]
        a dictionary (string, int) representing the type of ground-truths
        needed (logical AND among list elements).
        Each entry has the form `needed_ground_truth_type` as key
        and `level_of_truth` as value, where `needed_ground_truth_type` is the
        key of the ground_truth dictionary and `level_of_truth` is an int
        ranging from 0 to 2 (0->False, 1->True (manual annotation),
        2->True(automatic annotation)).
        If only part of a dataset contains a certain ground-truth type, you
        should use the `group` attribute to only select those songs.
    copy : bool
        If True, a new Dataset object is returned, and the calling one is
        leaved untouched

    Returns
    -------
    The input dataset as modified: `d = Dataset().filter(...)`
    If ``copy`` is True, return a new Dataset object.
    """
    if copy:
        ret = deepcopy(dataset)
    else:
        ret = dataset

    # let's remove everything and put only the wanted ones
    ret.paths = []

    end = 0
    for mydataset in ret.datasets:
        FLAG = True
        if not mydataset['included']:
            FLAG = False
        if len(datasets) > 0:
            if mydataset['name'] in datasets:
                FLAG = True
            else:
                FLAG = False

        # checking dataset-level filters
        if ensemble is not None:
            if ensemble != mydataset['ensemble']:
                FLAG = False

        for gt, val in ground_truth:
            if mydataset['ground_truth'][gt] != val:
                FLAG = False
                break

        if FLAG:
            ret._chunks[mydataset['name']] = [end, end]
            for song in mydataset['songs']:
                FLAG = True
                if not song['included']:
                    FLAG = False

                # checking song levels filters
                if instruments:
                    if instruments != song['instruments']:
                        FLAG = False

                if composer:
                    if composer not in song['composer']:
                        FLAG = False

                if groups:
                    for group in groups:
                        if group not in song['groups']:
                            FLAG = False
                            break

                if FLAG:
                    gts = song['ground_truth']
                    source = []
                    mix = []
                    if sources and "sources" in song.keys():
                        if all:
                            source = song['sources']['path']
                        else:
                            # find the index of the instrument
                            instrument = instruments[0]
                            idx = song['instruments'].index(instrument)

                            # take index of the target instrument
                            source = song['sources']['path'][idx]
                            gts = song['ground_truth'][idx]

                    if mixed:
                        mix = song['recording']['path']
                    ret.paths.append([mix, source, gts])
                    end += 1
                else:
                    song['included'] = False
            ret._chunks[mydataset['name']][1] = end
        else:
            mydataset['included'] = False

    return ret


def get_score_mat(dataset, idx, score_type=['misaligned']):
    """
    Get the score of a certain score, with times of `score_type`

    Arguments
    ---------
    idx : int
        The index of the song to retrieve.
    score_type : list of str
        The key to retrieve the list of notes from the ground_truths. see
        `chose_score_type` for explanation

    Returns
    -------
    numpy.ndarray :
        A (n x 6) array where columns represent pitches, onsets (seconds),
        offsets (seconds), velocities, MIDI program instrument and number of
        the instrument. Ordered by onsets. If some information is not
        available, value -255 is used.
    """

    gts = dataset.get_gts(idx)
    score_type = chose_score_type(score_type, gts)

    # print("    Loading ground truth " + score_type)
    mat = []
    for i, gt in enumerate(gts):

        # initilize each column
        pitches = np.array(gt[score_type]['pitches'])

        ons = np.array(gt[score_type]['onsets'])
        if not len(ons):
            ons = np.full_like(pitches, -255)

        missing = len(pitches) - len(ons)
        if missing < 0:
            # add -255 to pitches
            pitches = np.append(pitches, [-255] * -missing)
        elif missing > 0:
            # add -255 to ons
            ons = np.append(ons, [-255] * missing)

        offs = np.append(gt[score_type]['offsets'], [-255] * missing)
        if not len(offs):
            offs = np.full_like(ons, -255)

        vel = np.append(gt[score_type]['velocities'], [-255] * missing)
        if not len(vel):
            vel = np.full_like(ons, -255)
        missing = len(pitches) - len(vel)
        if missing < 0:
            # add -255 to pitches, ons and offs
            pitches = np.append(pitches, [-255] * -missing)
            ons = np.append(ons, [-255] * -missing)
            offs = np.append(offs, [-255] * -missing)
        elif missing > 0:
            # add -255 to vel
            vel = np.append(vel, [-255] * missing)

        num = np.full_like(ons, i)
        instr = np.full_like(ons, gt['instrument'])
        mat.append(np.array([pitches, ons, offs, vel, instr, num]))

    if len(mat) > 1:
        # mat now contains one list per each ground-truth, concatenating
        mat = np.concatenate(mat, axis=1)
    else:
        mat = np.array(mat[0])
    # transposing: one row per note
    mat = mat.T
    # ordering by onset
    mat = mat[mat[:, 1].argsort()]
    return mat


def get_pedaling_mat(dataset, idx, frame_based=False, winlen=0.046, hop=0.01):
    """
    Get data about pedaling

    Arguments
    ---------
    idx : int
        The index of the song to retrieve.
    frame_based : bool
        If True, the output will contain one row per frame, otherwise one
        row per control changes event.  Frames are deduced from `winlen` and
        `hop`.
    winlen : float
        The duration of a frame in seconds; only used if `frame_based` is
        True.
    hop : float
        The amount of hop-size in seconds; only used if `frame_based` is
        True.

    Returns
    -------
    list[np.ndarry] :
        list of 2d-arrays each listing all the control changes events in a
        track. Rows represent control changes or frames (according to
        `frame_based_option`) while columns represent (time, sustain value,
        sostenuto value, soft value).

        If `frame_based` is used, time is the central time of the frame and
        frames are computed using the most aligned score available for this
        item.

        If `frame_based` is False, value -1 is used for pedaling type not
        affected in a certain control change (i.e. a control change affects
        one type of pedaling, so the other two will have value -1).

        The output is sorted by time.
    """
    pedaling = []
    for gt in dataset.get_gts(idx):
        # take all cc...
        cc_track_pedaling = []
        for pedal in ['sustain', 'sostenuto', 'soft']:
            l = len(gt[pedal]['values'])
            if pedal == 'sustain':
                cc_track_pedaling += list(
                    zip(gt[pedal]['times'], gt[pedal]['values'], [-1] * l,
                        [-1] * l))
            elif pedal == 'sostenuto':
                cc_track_pedaling += list(
                    zip(gt[pedal]['times'], [-1] * l, gt[pedal]['values'],
                        [-1] * l))
            elif pedal == 'soft':
                cc_track_pedaling += list(
                    zip(gt[pedal]['times'], [-1] * l, [-1] * l,
                        gt[pedal]['values']))
        # sort cc according to time...
        cc_track_pedaling.sort(key=lambda row: row[0])
        cc_track_pedaling = np.array(cc_track_pedaling)

        if not frame_based:
            pedaling.append(cc_track_pedaling)
        else:
            # construct the frame-based output
            # compute the number of frames
            dur = dataset.get_score_duration(idx)
            n_frames = int(utils.nframes(dur, hop, winlen)) + 1

            # set up initial matrix that will be output
            frame_track_pedaling = np.zeros((n_frames, 4), dtype=float)
            # doesn't work because shape suffers from precisions problems
            # frame_track_pedaling[:, 0] = np.arange(winlen / 2, hop *
            # n_frames + winlen / 2, hop)
            frame_track_pedaling[:, 0] = np.arange(n_frames) * hop + winlen / 2

            # fill the matrix
            # rember the last value used for each column index:
            last_values = {
                1: {
                    "time": 0,
                    "value": 0
                },
                2: {
                    "time": 0,
                    "value": 0
                },
                3: {
                    "time": 0,
                    "value": 0
                },
            }
            # parse the control changes
            for cc in cc_track_pedaling:
                # compute the frame relative to this cc
                frame_idx = utils.time2frame(cc[0], hop, winlen)
                # put all values from last cc to this one equal to the last
                # value
                type_of_cc = np.argmax(cc[1:]) + 1
                frame_track_pedaling[
                    last_values[type_of_cc]["time"]:frame_idx,
                    type_of_cc] = last_values[type_of_cc]["value"]
                # update the last value
                last_values[type_of_cc]["time"] = frame_idx
                last_values[type_of_cc]["value"] = cc[type_of_cc]

            # put all values from last cc to the end equal to the last
            # value
            if len(cc_track_pedaling) > 0:
                for type_of_cc in range(1, 4):
                    frame_track_pedaling[
                        last_values[type_of_cc]["time"]:,
                        type_of_cc] = last_values[type_of_cc]["value"]
            pedaling.append(np.array(frame_track_pedaling))
    return pedaling