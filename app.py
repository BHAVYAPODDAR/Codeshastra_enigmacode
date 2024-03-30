import streamlit as st
import subprocess
import os




#
#    Copyright 2023 Picovoice Inc.
#
#    You may not use this file except in compliance with the license. A copy of the license is located in the "LICENSE"
#    file accompanying this source.
#
#    Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
#    an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
#    specific language governing permissions and limitations under the License.
#

import argparse
import contextlib
import os
import struct
import threading
import time
import wave

import pveagle
from pvrecorder import PvRecorder

from pvcheetah import create

PV_RECORDER_FRAME_LENGTH = 512

FEEDBACK_TO_DESCRIPTIVE_MSG = {
    pveagle.EagleProfilerEnrollFeedback.AUDIO_OK: 'Good audio',
    pveagle.EagleProfilerEnrollFeedback.AUDIO_TOO_SHORT: 'Insufficient audio length',
    pveagle.EagleProfilerEnrollFeedback.UNKNOWN_SPEAKER: 'Different speaker in audio',
    pveagle.EagleProfilerEnrollFeedback.NO_VOICE_FOUND: 'No voice found in audio',
    pveagle.EagleProfilerEnrollFeedback.QUALITY_ISSUE: 'Low audio quality due to bad microphone or environment'
}


class EnrollmentAnimation(threading.Thread):
    def __init__(self, sleep_time_sec=0.1):
        self._sleep_time_sec = sleep_time_sec
        self._frames = [
            " .  ",
            " .. ",
            " ...",
            "  ..",
            "   .",
            "    "
        ]
        self._done = False
        self._percentage = 0
        self._feedback = ''
        super().__init__()

    def run(self):
        self._done = False
        st.text("temoooo")
        while not self._done:
            for frame in self._frames:
                if self._done:
                    break
                st.text('\033[2K\033[1G\r[%3d%%]' % self._percentage + self._feedback + frame)
                time.sleep(self._sleep_time_sec)

    def stop(self):
        st.text('\033[2K\033[1G\r[%3d%%]' % self._percentage + self._feedback)
        self._done = True

    @property
    def percentage(self):
        return self._percentage

    @property
    def feedback(self):
        return self._feedback

    @percentage.setter
    def percentage(self, value):
        self._percentage = value

    @feedback.setter
    def feedback(self, value):
        self._feedback = value


def print_result(scores, labels):
    result = '\rscores -> '
    result += ', '.join('`%s`: %.2f' % (label, score) for label, score in zip(labels, scores))
    st.text(result)


def main(props):
    # parser = argparse.ArgumentParser()
    # parser.add_argument(
    #     '--show_audio_devices',
    #     action='store_true',
    #     help='List available audio input devices and exit')

    # common_parser = argparse.ArgumentParser(add_help=False)
    # common_parser.add_argument(
    #     '--access_key',
    #     required=True,
    #     help='AccessKey obtained from Picovoice Console (https://console.picovoice.ai/)')
    # common_parser.add_argument(
    #     '--library_path',
    #     help='Absolute path to dynamic library. Default: using the library provided by `pveagle`')
    # common_parser.add_argument(
    #     '--model_path',
    #     help='Absolute path to Eagle model. Default: using the model provided by `pveagle`')
    # common_parser.add_argument('--audio_device_index', type=int, default=-1, help='Index of input audio device')
    # common_parser.add_argument(
    #     '--output_audio_path',
    #     help='If provided, all recorded audio data will be saved to the given .wav file')

    # subparsers = parser.add_subparsers(dest='command')

    # enroll = subparsers.add_parser('enroll', help='Enroll a new speaker profile', parents=[common_parser])
    # enroll.add_argument(
    #     '--output_profile_path',
    #     required=True,
    #     help='Absolute path to output file for the created profile')

    # test = subparsers.add_parser(
    #     'test',
    #     help='Evaluate Eagle''s performance using the provided speaker profiles.',
    #     parents=[common_parser])
    # test.add_argument(
    #     '--input_profile_paths',
    #     required=True,
    #     nargs='+',
    #     help='Absolute path(s) to speaker profile(s)')

    # args = parser.parse_args()

    if props['show_audio_devices']:
        for index, name in enumerate(PvRecorder.get_available_devices()):
            st.text('Device #%d: %s' % (index, name))
        return

    if props['command'] == 'enroll':
        try:
            eagle_profiler = pveagle.create_profiler(access_key=props['access_key'])
        except pveagle.EagleError as e:
            st.text("Failed to initialize Eagle: %s" % e)
            raise

        st.text('Eagle version: %s' % eagle_profiler.version)
        recorder = PvRecorder(frame_length=PV_RECORDER_FRAME_LENGTH, device_index=props['audio_device_index'])
        st.text("Recording audio from '%s'" % recorder.selected_device)
        num_enroll_frames = eagle_profiler.min_enroll_samples // PV_RECORDER_FRAME_LENGTH
        sample_rate = eagle_profiler.sample_rate
        enrollment_animation = EnrollmentAnimation()
        st.text('Please keep speaking until the enrollment percentage reaches 100%')
        try:
            with contextlib.ExitStack() as file_stack:
                enroll_percentage = 0.0
                enrollment_animation.start()
                
                enroll_message = st.empty()
                
                while enroll_percentage < 100.0:
                    enroll_pcm = list()
                    recorder.start()
                    for _ in range(num_enroll_frames):
                        input_frame = recorder.read()
                        enroll_pcm.extend(input_frame)
                    recorder.stop()

                    enroll_percentage, feedback = eagle_profiler.enroll(enroll_pcm)
                    enrollment_animation.percentage = enroll_percentage
                    enroll_message.text(str(enrollment_animation.percentage) + '% - ' + str(FEEDBACK_TO_DESCRIPTIVE_MSG[feedback]))
                    enrollment_animation.feedback = ' - %s' % FEEDBACK_TO_DESCRIPTIVE_MSG[feedback]

            speaker_profile = eagle_profiler.export()
            enrollment_animation.stop()
            with open(props['output_profile_path'], 'wb') as f:
                f.write(speaker_profile.to_bytes())
            st.text('\nSpeaker profile is saved to %s' % props['output_profile_path'])

        except KeyboardInterrupt:
            st.text('\nStopping enrollment. No speaker profile is saved.')
            enrollment_animation.stop()
        except pveagle.EagleActivationLimitError:
            st.text('AccessKey has reached its processing limit')
        except pveagle.EagleError as e:
            st.text('Failed to enroll speaker: %s' % e)
        finally:
            recorder.stop()
            recorder.delete()
            eagle_profiler.delete()

    elif props['command'] == 'test':
        profiles = list()
        speaker_labels = list()
        for profile_path in props['input_profile_paths']:
            speaker_labels.append(os.path.splitext(os.path.basename(profile_path))[0])
            with open(profile_path, 'rb') as f:
                profile = pveagle.EagleProfile.from_bytes(f.read())
            profiles.append(profile)

        eagle = None
        recorder = None
        
        cheetah = create(
            access_key=props['access_key'],
            endpoint_duration_sec=props['endpoint_duration_sec'],
            enable_automatic_punctuation=not props['disable_automatic_punctuation']
        )
        
        try:
            eagle = pveagle.create_recognizer(
                access_key=props['access_key'],
                speaker_profiles=profiles
            )

            recorder = PvRecorder(device_index=props['audio_device_index'], frame_length=eagle.frame_length)
            recorder.start()

            with contextlib.ExitStack() as file_stack:
                st.text('Listening for audio... (press Ctrl+C to stop)')
                
                test_message = st.empty()
                spoken_text = st.empty()
                
                while True:
                    pcm = recorder.read()
                    
                    partial_transcript, is_endpoint = cheetah.process(pcm)
                    
                    if is_endpoint:
                        test_message.text(cheetah.flush())
                    
                    scores = eagle.process(pcm)
                    
                    result = '\rscores -> '
                    result += ', '.join('`%s`: %.2f' % (label, score) for label, score in zip(speaker_labels, scores))
                    
                    spoken_text.text('text: ' + str(partial_transcript))
                    
                    test_message.text(result)

        except KeyboardInterrupt:
            st.text('\nStopping...')
        except pveagle.EagleActivationLimitError:
            st.text('\nAccessKey has reached its processing limit')
        finally:
            if eagle is not None:
                eagle.delete()
            if recorder is not None:
                recorder.stop()
                recorder.delete()

    else:
        st.text('Please specify a mode: enroll or test')
        return


# Define the directory where you want to save the profiles
profiles_dir = "profiles"
os.makedirs(profiles_dir, exist_ok=True)

st.title("Speaker Enrollment")

page = st.sidebar.radio("Select a page", ["Enroll", "Test"])
# Input for username

if page == "Enroll":
    username = st.text_input("Enter a username:")

    # Button to start the enrollment process
    if st.button("Enroll Speaker"):
        if username:  # Ensure the username is not empty
            output_file_path = os.path.join(profiles_dir, f"{username}.txt")            
            
            try:
                # Use subprocess to execute the command
                # process = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                props = {
                    'command': 'enroll',
                    'access_key': 'CgL1JCFdKQi7VoeeNtclpgaIb6LSZd0esC7xs3dl8bl59PRC+T7NyQ==',
                    'audio_device_index': -1,
                    'output_profile_path': output_file_path,
                    'input_profile_paths': output_file_path,
                    'show_audio_devices': False,
                    'output_audio_path': None
                }
                process = main(props)
                
                # Display the output to the user
                st.success("Enrollment Successful!")
                # st.text(process.stdout)
            except subprocess.CalledProcessError as e:
                st.error("Enrollment Failed")
                st.text(e.stderr)
        else:
            st.warning("Please enter a username.")

elif page == 'Test':
    if st.button("Test Speaker"):        
        users = ['profiles/' + f for f in os.listdir(os.path.join(profiles_dir)) if f.endswith('.txt')]       
        
        try:
            # Use subprocess to execute the command
            # process = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            props = {
                'command': 'test',
                'access_key': 'CgL1JCFdKQi7VoeeNtclpgaIb6LSZd0esC7xs3dl8bl59PRC+T7NyQ==',
                'audio_device_index': -1,
                'input_profile_paths': users,
                'show_audio_devices': False,
                'output_audio_path': None,
                'endpoint_duration_sec': 1.,
                'disable_automatic_punctuation': True
            }
            
            process = main(props)
            
            # Display the output to the user
            st.success("Enrollment Successful!")
            # st.text(process.stdout)
        except subprocess.CalledProcessError as e:
            st.error("Enrollment Failed")
            st.text(e.stderr)
