from kokoro_onnx import Kokoro
import inspect

def test_kokoro_features():
    model_path = "kokoro-v1.0.onnx"
    voices_path = "voices-v1.0.bin"
    
    try:
        kokoro = Kokoro(model_path, voices_path)
        print("Methods in Kokoro class:")
        for name, method in inspect.getmembers(kokoro, predicate=inspect.ismethod):
            print(f" - {name}{inspect.signature(method)}")
            
        # Try to call create with a short text and see what it returns
        # Usually: samples, sample_rate = create(...)
        # Maybe there is a parameter for timestamps?
        print("\nTesting 'create' return values:")
        res = kokoro.create("Hello.", voice="af_bella", speed=1.0, lang="en-us")
        print(f"Type of return: {type(res)}")
        if isinstance(res, tuple):
            print(f"Tuple length: {len(res)}")
            for i, val in enumerate(res):
                print(f" - Item {i} type: {type(val)}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_kokoro_features()
