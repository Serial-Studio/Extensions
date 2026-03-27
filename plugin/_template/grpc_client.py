"""
Serial Studio gRPC Client

Drop-in replacement for the TCP APIClient. Connects to the Serial Studio
gRPC server on port 8888 for high-performance frame streaming.

Usage:
    client = GRPCClient()
    client.on_frame = my_frame_callback  # called with frame dict
    client.on_raw = my_raw_callback      # called with (bytes, timestamp_ms)
    threading.Thread(target=client.run_loop, daemon=True).start()
"""

import sys
import time
import threading
from pathlib import Path

try:
    import grpc
except ImportError:
    sys.exit(
        "[gRPC] grpcio not installed. Run: pip install grpcio grpcio-tools"
    )

# Import generated stubs from the same directory
_here = Path(__file__).parent
sys.path.insert(0, str(_here))
import serialstudio_pb2 as pb
import serialstudio_pb2_grpc as rpc


class GRPCClient:
    """Streams frames and raw data from Serial Studio via gRPC."""

    def __init__(self, host="localhost", port=8888):
        self.target = f"{host}:{port}"
        self.running = True
        self.connected = False
        self.on_frame = None
        self.on_raw = None
        self._channel = None
        self._stub = None

    def connect(self):
        """Establish gRPC channel."""
        try:
            self._channel = grpc.insecure_channel(
                self.target,
                options=[
                    ("grpc.max_receive_message_length", 16 * 1024 * 1024),
                ],
            )
            grpc.channel_ready_future(self._channel).result(timeout=3)
            self._stub = rpc.SerialStudioAPIStub(self._channel)
            self.connected = True
            return True
        except Exception:
            self.connected = False
            return False

    def execute(self, command, params=None):
        """Execute a single API command. Returns (success, result_or_error)."""
        if not self._stub:
            return False, "Not connected"

        req = pb.CommandRequest(id="1", command=command)
        if params:
            req.params.update(params)

        try:
            resp = self._stub.ExecuteCommand(req, timeout=5)
            if resp.success:
                return True, resp.result
            return False, f"{resp.error.code}: {resp.error.message}"
        except grpc.RpcError as e:
            return False, str(e)

    def run_loop(self):
        """Main loop: connect and stream frames + raw data. Auto-reconnects."""
        while self.running:
            if not self.connected:
                time.sleep(2)
                self.connect()
                continue

            # Start raw data stream on a separate thread if callback is set
            if self.on_raw:
                threading.Thread(
                    target=self._raw_loop, daemon=True).start()

            try:
                stream = self._stub.StreamFrames(pb.StreamRequest())
                for batch in stream:
                    if not self.running:
                        break

                    if self.on_frame:
                        for frame_data in batch.frames:
                            frame = _struct_to_dict(frame_data.frame)
                            self.on_frame(frame)

            except grpc.RpcError:
                self.connected = False
                continue

    def _raw_loop(self):
        """Stream raw device data. Runs on a separate thread."""
        try:
            stream = self._stub.StreamRawData(pb.StreamRequest())
            for batch in stream:
                if not self.running:
                    break

                if self.on_raw:
                    for packet in batch.packets:
                        self.on_raw(packet.data, packet.timestamp_ms)

        except grpc.RpcError:
            pass

    def stop(self):
        """Shutdown the client."""
        self.running = False
        if self._channel:
            self._channel.close()


def _struct_to_dict(struct):
    """Convert google.protobuf.Struct to a Python dict."""
    from google.protobuf.json_format import MessageToDict
    return MessageToDict(struct)
