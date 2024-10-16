# vim: ts=4 sw=4 et ai:
# -*- coding: utf8 -*-
"""This module implements the TFTP Client functionality. Instantiate an
instance of the client, and then use its upload or download method. Logging is
performed via a standard logging object set in TftpShared."""


import io
import types
import logging
from .TftpShared import *
from .TftpPacketTypes import *
from .TftpContexts import TftpContextClientDownload, TftpContextClientUpload

log = logging.getLogger('tftpy.TftpClient')

class TftpClient(TftpSession):
    """This class is an implementation of a tftp client. Once instantiated, a
    download can be initiated via the download() method, or an upload via the
    upload() method."""

    def __init__(self, host, port=69, options={}, localip = ""):
        TftpSession.__init__(self)
        self.context = None
        self.host = host
        self.iport = port
        self.filename = None
        self.options = options
        self.localip = localip
        if 'blksize' in self.options:
            size = self.options['blksize']
            tftpassert(int == type(size), "blksize must be an int")
            if size < MIN_BLKSIZE or size > MAX_BLKSIZE:
                raise TftpException("Invalid blksize: %d" % size)

    def download(self, filename, output, packethook=None, timeout=SOCK_TIMEOUT, retries=DEF_TIMEOUT_RETRIES):
        """This method initiates a tftp download from the configured remote
        host, requesting the filename passed. It writes the file to output,
        which can be a file-like object or a path to a local file. If a
        packethook is provided, it must be a function that takes a single
        parameter, which will be a copy of each DAT packet received in the
        form of a TftpPacketDAT object. The timeout parameter may be used to
        override the default SOCK_TIMEOUT setting, which is the amount of time
        that the client will wait for a receive packet to arrive.
        The retires paramater may be used to override the default DEF_TIMEOUT_RETRIES
        settings, which is the amount of retransmission attemtpts the client will initiate
        after encountering a timeout.

        Note: If output is a hyphen, stdout is used."""
        # We're downloading.
        log.debug("Creating download context with the following params:")
        log.debug("host = %s, port = %s, filename = %s" % (self.host, self.iport, filename))
        log.debug("options = %s, packethook = %s, timeout = %s" % (self.options, packethook, timeout))
        self.context = TftpContextClientDownload(self.host,
                                                 self.iport,
                                                 filename,
                                                 output,
                                                 self.options,
                                                 packethook,
                                                 timeout,
                                                 retries=retries,
                                                 localip=self.localip)
        self.context.start()
        # Download happens here
        self.context.end()

        metrics = self.context.metrics

        log.info('')
        log.info("Download complete.")
        if metrics.duration == 0:
            log.info("Duration too short, rate undetermined")
        else:
            log.info("Downloaded %.2f bytes in %.2f seconds" % (metrics.bytes, metrics.duration))
            log.info("Average rate: %.2f kbps" % metrics.kbps)
        log.info("%.2f bytes in resent data" % metrics.resent_bytes)
        log.info("Received %d duplicate packets" % metrics.dupcount)
    def get_file_size(self, filename):
        """Simulate a request to get the file size from the server."""
        # Create a request for the file
        try:
            # Here you would typically send a request to the server to check if the file exists
            # Since TFTP doesn't support file size queries, we can simply perform a download in a way
            # that we can track the size without saving the file, just for demonstration.
            output = io.BytesIO()  # Use a BytesIO object to avoid writing to disk
            self.download(filename, output)

            # Get the size of the downloaded data
            return output.getbuffer().nbytes

        except Exception as e:
            log.error(f"Failed to get file size: {str(e)}")
            return -1  # Return -1 or another sentinel value to indicate an error
    def upload(self, filename, input, packethook=None, timeout=SOCK_TIMEOUT, retries=DEF_TIMEOUT_RETRIES):
        """This method initiates a tftp upload to the configured remote host,
        uploading the filename passed. It reads the file from input, which
        can be a file-like object or a path to a local file. If a packethook
        is provided, it must be a function that takes a single parameter,
        which will be a copy of each DAT packet sent in the form of a
        TftpPacketDAT object. The timeout parameter may be used to override
        the default SOCK_TIMEOUT setting, which is the amount of time that
        the client will wait for a DAT packet to be ACKd by the server.
        The retires paramater may be used to override the default DEF_TIMEOUT_RETRIES
        settings, which is the amount of retransmission attemtpts the client will initiate
        after encountering a timeout.

        Note: If input is a hyphen, stdin is used."""
        self.context = TftpContextClientUpload(self.host,
                                               self.iport,
                                               filename,
                                               input,
                                               self.options,
                                               packethook,
                                               timeout,
                                               retries=retries,
                                               localip=self.localip)
        self.context.start()
        # Upload happens here
        self.context.end()

        metrics = self.context.metrics

        log.info('')
        log.info("Upload complete.")
        if metrics.duration == 0:
            log.info("Duration too short, rate undetermined")
        else:
            log.info("Uploaded %d bytes in %.2f seconds" % (metrics.bytes, metrics.duration))
            log.info("Average rate: %.2f kbps" % metrics.kbps)
        log.info("%.2f bytes in resent data" % metrics.resent_bytes)
        log.info("Resent %d packets" % metrics.dupcount)