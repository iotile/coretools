# BLED112 Dongle Capability Notes

## Introduction

This document summarizes specific learnings about what the BLED112 dongle can and cannot do as well as other important
hardware notes and limitations.

## Important Notes

1. You can scan and receive advertisements while connected to a peripheral.  We had previously been under the impression
   that scanning was impossible when connected but using the `scripts/bled112_observer.py` test script indicates that
