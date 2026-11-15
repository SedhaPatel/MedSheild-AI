---
title: MedShield
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
short_description: De-identify, encrypt and triage chest X-rays (research demo)
---

# MedShield: chest X-ray triage

Upload a chest X-ray (DICOM, PNG or JPEG). MedShield removes patient identifiers from the file and the image,
encrypts the result, and scores it for five findings (pneumonia, cardiomegaly, pleural effusion, pneumothorax,
atelectasis) with a pre-trained DenseNet-121, including heatmaps and a question-and-answer assistant.

**Research and demo use only. Not a diagnostic device.** Do not upload real patient data to a public Space.

Uploaded studies live only for the life of the container; they are lost when the Space restarts or sleeps.
