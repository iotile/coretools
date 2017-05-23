"""Globally available processing functions that can be used in sensor graph nodes.

These functions should not be used directly but rather will be invoked by name
when creating a sensor graph node inside the SensorGraph class.  They are found
by looking at the installed python packages using pkg_resources.
"""

def copy_all_a(input_a, *other_inputs):
    """Copy all readings in input a into the output.

    All other inputs are skipped so that after this function
    runs there are no readings left in any of the input walkers
    when the function finishes, even if it generated no output
    readings.
    """

    output = []
    while input_a.count() > 0:
        output.append(input_a.pop())

    for input_x in other_inputs:
        input_x.skip_all()

    return output
