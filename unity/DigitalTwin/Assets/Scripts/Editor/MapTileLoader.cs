using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using GaussianSplatting.Runtime;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DigitalTwin
{
    /// <summary>
    /// data/maps/&lt;name&gt;/tiles.json を読み、タイルごとに 3DGS の描画用アセットを作って
    /// 開いているシーンに並べるエディタ専用のメニュー（E2-2）。
    /// 作成はパッケージの GaussianSplatAssetCreator に任せる（非公開の名前はリフレクションで使う）。
    /// </summary>
    public class MapTileLoader : EditorWindow
    {
        const string kMenuPath = "Tools/Digital Twin/Load Map Tiles";
        const string kDefaultMapName = "map";
        const string kProgressTitle = "Load Map Tiles";
        const string kStateFile = "import_state.json";
        const string kCreatorType = "GaussianSplatting.Editor.GaussianSplatAssetCreator";
        static readonly string[] kBytesSuffixes = { "_chk", "_pos", "_oth", "_col", "_shs" };

        [Serializable]
        class TileEntry
        {
            public string file;
            public string sha256;
        }

        [Serializable]
        class TilesFile
        {
            public TileEntry[] tiles;
        }

        string m_MapName = kDefaultMapName;

        [MenuItem(kMenuPath)]
        static void Open()
        {
            var window = GetWindow<MapTileLoader>(true, "Load Map Tiles");
            window.minSize = new Vector2(320, 80);
            window.maxSize = new Vector2(480, 100);
        }

        void OnGUI()
        {
            m_MapName = EditorGUILayout.TextField("Map name", m_MapName);
            if (GUILayout.Button("Load"))
            {
                LoadMap(m_MapName.Trim());
            }
        }

        // ---------------------------------------------------------------- 読み込み全体

        static void LoadMap(string mapName)
        {
            if (string.IsNullOrEmpty(mapName))
            {
                Debug.LogError("[MapTileLoader] map name is empty");
                return;
            }

            // Application.dataPath = <repo>/unity/DigitalTwin/Assets
            string projectDir = Path.GetDirectoryName(Application.dataPath);
            string repoRoot = Path.GetFullPath(Path.Combine(projectDir, "..", ".."));
            string mapDir = Path.Combine(repoRoot, "data", "maps", mapName);
            string tilesJsonPath = Path.Combine(mapDir, "tiles.json");
            if (!File.Exists(tilesJsonPath))
            {
                Debug.LogError($"[MapTileLoader] tiles.json not found: {tilesJsonPath}");
                return;
            }

            var tilesFile = JsonUtility.FromJson<TilesFile>(File.ReadAllText(tilesJsonPath));
            if (tilesFile == null || tilesFile.tiles == null)
            {
                Debug.LogError($"[MapTileLoader] no tiles in {tilesJsonPath}");
                return;
            }

            string outFolder = $"Assets/Map/Generated/{mapName}";
            string statePath = Path.Combine(projectDir, outFolder, kStateFile);

            int created = 0, skipped = 0, removed = 0, failed = 0;
            var ok = new Dictionary<string, GaussianSplatAsset>(); // タイル名 -> アセット
            ScriptableObject creator = null;
            try
            {
                var state = ReadState(statePath);
                var current = new HashSet<string>();
                foreach (var t in tilesFile.tiles)
                {
                    current.Add(Path.GetFileNameWithoutExtension(t.file));
                }

                // tiles.json からなくなったタイルを消す
                removed = RemoveStale(outFolder, projectDir, state, current);

                Directory.CreateDirectory(Path.Combine(projectDir, outFolder));

                var fields = new CreatorAccess();
                if (tilesFile.tiles.Length > 0)
                {
                    creator = fields.Create();
                    if (creator == null)
                    {
                        failed = tilesFile.tiles.Length;
                        return;
                    }
                }

                for (int i = 0; i < tilesFile.tiles.Length; i++)
                {
                    var tile = tilesFile.tiles[i];
                    string tileName = Path.GetFileNameWithoutExtension(tile.file);
                    string assetPath = $"{outFolder}/{tileName}.asset";
                    EditorUtility.DisplayProgressBar(kProgressTitle, $"{tileName} ({i + 1}/{tilesFile.tiles.Length})",
                        (float)i / tilesFile.tiles.Length);

                    bool upToDate = state.TryGetValue(tile.file, out var recorded) && recorded == tile.sha256
                        && File.Exists(Path.Combine(projectDir, assetPath));
                    if (upToDate)
                    {
                        skipped++;
                    }
                    else
                    {
                        string plyPath = Path.GetFullPath(Path.Combine(mapDir, tile.file));
                        string error = fields.CreateAsset(creator, plyPath, outFolder);
                        if (error != null)
                        {
                            Debug.LogError($"[MapTileLoader] {tileName}: {error}");
                            failed++;
                            continue;
                        }
                        state[tile.file] = tile.sha256;
                        created++;
                        WriteState(statePath, state); // 途中で止まっても作った分は残す
                    }

                    AssetDatabase.ImportAsset(assetPath);
                    var asset = AssetDatabase.LoadAssetAtPath<GaussianSplatAsset>(assetPath);
                    if (asset != null)
                    {
                        ok[tileName] = asset;
                    }
                    else
                    {
                        Debug.LogError($"[MapTileLoader] could not load asset: {assetPath}");
                    }
                }

                WriteState(statePath, state);
                AssetDatabase.SaveAssets();
                AssetDatabase.Refresh();

                PlaceInScene(mapName, current, ok);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[MapTileLoader] failed: {ex}");
            }
            finally
            {
                if (creator != null)
                {
                    DestroyImmediate(creator);
                }
                EditorUtility.ClearProgressBar();
            }

            Debug.Log($"[MapTileLoader] map '{mapName}': created {created}, kept {skipped}, removed {removed}, failed {failed}");
        }

        // ---------------------------------------------------------------- import_state.json

        static Dictionary<string, string> ReadState(string path)
        {
            var state = new Dictionary<string, string>();
            if (!File.Exists(path))
            {
                return state;
            }
            foreach (Match m in Regex.Matches(File.ReadAllText(path), "\"([^\"]+)\"\\s*:\\s*\"([^\"]*)\""))
            {
                state[m.Groups[1].Value] = m.Groups[2].Value;
            }
            return state;
        }

        static void WriteState(string path, Dictionary<string, string> state)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var keys = new List<string>(state.Keys);
            keys.Sort(StringComparer.Ordinal);
            var sb = new StringBuilder("{\n");
            for (int i = 0; i < keys.Count; i++)
            {
                sb.Append($"  \"{keys[i]}\": \"{state[keys[i]]}\"");
                sb.Append(i + 1 < keys.Count ? ",\n" : "\n");
            }
            sb.Append("}\n");
            File.WriteAllText(path, sb.ToString());
        }

        // ---------------------------------------------------------------- 古いアセットの削除

        static int RemoveStale(string outFolder, string projectDir, Dictionary<string, string> state, HashSet<string> current)
        {
            var staleNames = new HashSet<string>();
            var staleKeys = new List<string>();
            foreach (var key in state.Keys)
            {
                string n = Path.GetFileNameWithoutExtension(key);
                if (!current.Contains(n))
                {
                    staleNames.Add(n);
                    staleKeys.Add(key);
                }
            }
            string absFolder = Path.Combine(projectDir, outFolder);
            if (Directory.Exists(absFolder))
            {
                foreach (var f in Directory.GetFiles(absFolder, "*.asset"))
                {
                    string n = Path.GetFileNameWithoutExtension(f);
                    if (!current.Contains(n))
                    {
                        staleNames.Add(n);
                    }
                }
            }

            foreach (var n in staleNames)
            {
                AssetDatabase.DeleteAsset($"{outFolder}/{n}.asset");
                foreach (var suffix in kBytesSuffixes)
                {
                    AssetDatabase.DeleteAsset($"{outFolder}/{n}{suffix}.bytes");
                }
            }
            foreach (var key in staleKeys)
            {
                state.Remove(key);
            }
            return staleNames.Count;
        }

        // ---------------------------------------------------------------- シーンへの配置

        static void PlaceInScene(string mapName, HashSet<string> currentTiles, Dictionary<string, GaussianSplatAsset> assets)
        {
            Scene scene = SceneManager.GetActiveScene();
            string rootName = $"Map_{mapName}";

            GameObject root = null;
            foreach (var go in scene.GetRootGameObjects())
            {
                if (go.name == rootName)
                {
                    root = go;
                    break;
                }
            }
            if (root == null)
            {
                // 新しく作った場合だけ変換を決める（既存の変換は位置合わせの値なので変えない）。
                // 回転は仮の値（地図の座標は y が下向き）。
                root = new GameObject(rootName);
                root.transform.SetPositionAndRotation(Vector3.zero, Quaternion.Euler(180f, 0f, 0f));
                root.transform.localScale = Vector3.one;
                Undo.RegisterCreatedObjectUndo(root, "Create map root");
            }

            // tiles.json にない子を消す
            for (int i = root.transform.childCount - 1; i >= 0; i--)
            {
                var child = root.transform.GetChild(i).gameObject;
                if (!currentTiles.Contains(child.name))
                {
                    DestroyImmediate(child);
                }
            }

            foreach (var pair in assets)
            {
                var childTr = root.transform.Find(pair.Key);
                GameObject child;
                if (childTr != null)
                {
                    child = childTr.gameObject;
                }
                else
                {
                    child = new GameObject(pair.Key);
                    child.transform.SetParent(root.transform, false);
                    child.transform.localPosition = Vector3.zero;
                    child.transform.localRotation = Quaternion.identity;
                    child.transform.localScale = Vector3.one;
                }
                var renderer = child.GetComponent<GaussianSplatRenderer>();
                if (renderer == null)
                {
                    renderer = child.AddComponent<GaussianSplatRenderer>();
                }
                renderer.m_Asset = pair.Value;
                EditorUtility.SetDirty(renderer);
            }

            EditorSceneManager.MarkSceneDirty(scene);
        }

        // ---------------------------------------------------------------- GaussianSplatAssetCreator のリフレクション

        /// <summary>
        /// パッケージ v1.1.2 の GaussianSplatAssetCreator の非公開の名前
        /// （m_InputFile・m_OutputFolder・m_Quality・m_ErrorMessage・CreateAsset）を使う。
        /// </summary>
        class CreatorAccess
        {
            const BindingFlags kFlags = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;

            Type m_Type;
            FieldInfo m_InputFile, m_OutputFolder, m_Quality, m_ErrorMessage;
            MethodInfo m_CreateAsset;

            public ScriptableObject Create()
            {
                m_Type = FindType(kCreatorType);
                if (m_Type == null)
                {
                    Debug.LogError($"[MapTileLoader] type not found: {kCreatorType}");
                    return null;
                }

                m_InputFile = m_Type.GetField("m_InputFile", kFlags);
                m_OutputFolder = m_Type.GetField("m_OutputFolder", kFlags);
                m_Quality = m_Type.GetField("m_Quality", kFlags);
                m_ErrorMessage = m_Type.GetField("m_ErrorMessage", kFlags);
                m_CreateAsset = m_Type.GetMethod("CreateAsset", kFlags);

                var missing = new List<string>();
                if (m_InputFile == null) missing.Add("m_InputFile");
                if (m_OutputFolder == null) missing.Add("m_OutputFolder");
                if (m_Quality == null) missing.Add("m_Quality");
                if (m_ErrorMessage == null) missing.Add("m_ErrorMessage");
                if (m_CreateAsset == null) missing.Add("CreateAsset");
                if (missing.Count > 0)
                {
                    Debug.LogError($"[MapTileLoader] not found in {kCreatorType}: {string.Join(", ", missing)}");
                    return null;
                }

                object medium;
                try
                {
                    medium = Enum.Parse(m_Quality.FieldType, "Medium");
                }
                catch (ArgumentException)
                {
                    Debug.LogError("[MapTileLoader] quality 'Medium' not found in m_Quality");
                    return null;
                }

                var instance = ScriptableObject.CreateInstance(m_Type);
                m_Quality.SetValue(instance, medium);
                return instance;
            }

            /// <summary>作成に成功すれば null、失敗すればエラーの文を返す。</summary>
            public string CreateAsset(ScriptableObject instance, string inputFile, string outputFolder)
            {
                m_InputFile.SetValue(instance, inputFile);
                m_OutputFolder.SetValue(instance, outputFolder);
                m_ErrorMessage.SetValue(instance, null);
                try
                {
                    m_CreateAsset.Invoke(instance, null);
                }
                catch (TargetInvocationException ex)
                {
                    return (ex.InnerException ?? ex).Message;
                }
                var message = m_ErrorMessage.GetValue(instance) as string;
                return string.IsNullOrEmpty(message) ? null : message;
            }

            static Type FindType(string fullName)
            {
                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    var t = asm.GetType(fullName, false);
                    if (t != null)
                    {
                        return t;
                    }
                }
                return null;
            }
        }
    }
}
