import importlib.util
import tempfile
import unittest
from pathlib import Path

LAUNCH = Path(__file__).parent.parent / "llama_cpp/rootfs/usr/lib/llama-app/launch.py"
spec = importlib.util.spec_from_file_location("launch", LAUNCH)
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)

BASE = ["/app/llama-server", "--host", "0.0.0.0", "--port", "8080"]


class BuildArgv(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.models = Path(tmp.name) / "models"
        self.models.mkdir()

    def argv(self, **options):
        return launch.build_argv(options, self.models)

    def test_no_model_is_router_mode(self):
        expected = BASE + ["--models-dir", str(self.models)]
        self.assertEqual(self.argv(), expected)
        self.assertEqual(self.argv(model=""), expected)

    def test_hugging_face_reference(self):
        for ref in ("ggml-org/gemma-3-1b-it-GGUF", "ggml-org/gemma-3-1b-it-GGUF:Q4_K_M"):
            self.assertEqual(self.argv(model=ref), BASE + ["--hf-repo", ref])

    def test_local_file(self):
        (self.models / "tiny.gguf").touch()
        path = str((self.models / "tiny.gguf").resolve())
        self.assertEqual(self.argv(model="tiny.gguf"), BASE + ["--model", path])

    def test_local_file_in_subdirectory(self):
        (self.models / "vision").mkdir()
        (self.models / "vision" / "model.gguf").touch()
        path = str((self.models / "vision" / "model.gguf").resolve())
        self.assertEqual(self.argv(model="vision/model.gguf"), BASE + ["--model", path])

    def test_missing_local_file_is_rejected(self):
        with self.assertRaisesRegex(launch.ConfigError, "does not exist"):
            self.argv(model="absent.gguf")

    def test_file_outside_models_dir_is_rejected(self):
        (self.models.parent / "secret.gguf").touch()
        with self.assertRaisesRegex(launch.ConfigError, "outside"):
            self.argv(model="../secret.gguf")

    def test_unrecognised_model_is_rejected(self):
        for bad in ("just-a-name", "a/b/c", "user/repo:quant:extra", "user/re po"):
            with self.assertRaises(launch.ConfigError, msg=bad):
                self.argv(model=bad)

    def test_tuning_options_pass_through(self):
        self.assertEqual(
            self.argv(context_size=8192, gpu_layers="all", threads=4, parallel=2),
            BASE
            + ["--models-dir", str(self.models)]
            + ["--ctx-size", "8192", "--n-gpu-layers", "all"]
            + ["--threads", "4", "--parallel", "2"],
        )

    def test_zero_is_passed_not_dropped(self):
        argv = self.argv(context_size=0, gpu_layers="0")
        self.assertIn("--ctx-size", argv)
        self.assertEqual(argv[argv.index("--n-gpu-layers") + 1], "0")

    def test_extra_args_come_last_and_are_shell_split(self):
        argv = self.argv(threads=4, extra_args='--alias "my model" --threads 8')
        self.assertEqual(argv[-4:], ["--alias", "my model", "--threads", "8"])

    def test_unbalanced_extra_args_are_rejected(self):
        with self.assertRaisesRegex(launch.ConfigError, "extra_args"):
            self.argv(extra_args='--alias "unterminated')


class Preload(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.models = Path(tmp.name) / "models"
        self.models.mkdir()
        (self.models / "tiny.gguf").touch()
        (self.models / "vision").mkdir()
        (self.models / "notes.txt").touch()

    def test_preload_adds_the_preset_in_router_mode(self):
        argv = launch.build_argv({"preload": ["tiny"]}, self.models, Path("/p.ini"))
        self.assertEqual(argv[-2:], ["--models-preset", "/p.ini"])

    def test_empty_preload_adds_nothing(self):
        argv = launch.build_argv({"preload": []}, self.models)
        self.assertNotIn("--models-preset", argv)

    def test_preload_is_ignored_with_a_model_set(self):
        argv = launch.build_argv({"model": "tiny.gguf", "preload": ["tiny"]}, self.models)
        self.assertNotIn("--models-preset", argv)

    def test_extra_args_still_come_after_the_preset(self):
        argv = launch.build_argv({"preload": ["tiny"], "extra_args": "--threads 8"}, self.models)
        self.assertEqual(argv[-2:], ["--threads", "8"])

    def test_preset_names_files_directories_and_references(self):
        text = launch.preset_text(["tiny.gguf", "vision", "user/repo:Q4_K_M"], self.models)
        self.assertEqual(
            text,
            "version = 1\n\n"
            "[tiny]\nload-on-startup = true\n\n"
            "[vision]\nload-on-startup = true\n\n"
            "[user/repo:Q4_K_M]\nload-on-startup = true\n",
        )

    def test_unknown_names_are_rejected(self):
        for bad in ("absent", "notes", "notes.txt", "tiny]\n[x"):
            with self.assertRaisesRegex(launch.ConfigError, "preload", msg=bad):
                launch.preset_text([bad], self.models)


class BuildEnv(unittest.TestCase):
    def test_cache_dir_is_always_set(self):
        env = launch.build_env({}, {"PATH": "/bin"}, Path("/share/llama_cpp/cache"))
        self.assertEqual(env, {"PATH": "/bin", "LLAMA_CACHE": "/share/llama_cpp/cache"})

    def test_secrets_go_to_the_environment(self):
        env = launch.build_env({"api_key": "k", "hf_token": "hf_t"}, {}, Path("/c"))
        self.assertEqual(env["LLAMA_API_KEY"], "k")
        self.assertEqual(env["HF_TOKEN"], "hf_t")

    def test_empty_secrets_are_not_set(self):
        env = launch.build_env({"api_key": "", "hf_token": ""}, {}, Path("/c"))
        self.assertNotIn("LLAMA_API_KEY", env)
        self.assertNotIn("HF_TOKEN", env)

    def test_secrets_never_reach_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = launch.build_argv({"api_key": "sekrit", "hf_token": "hf_sekrit"}, Path(tmp))
        self.assertFalse([a for a in argv if "sekrit" in a])


if __name__ == "__main__":
    unittest.main()
