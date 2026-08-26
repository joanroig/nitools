import struct
import re
import os
import json
import zlib
import base64
import binascii
from typing import Dict, List, Any, Optional, Tuple

class IntelligentDecoder:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = None
        self.parsed_data = {}

    def load_file(self):
        """Load the nbkt file into memory"""
        with open(self.file_path, 'rb') as f:
            self.data = f.read()
        print(f"[+] Loaded {len(self.data)} bytes from {self.file_path}")

    def analyze_file_structure(self) -> Dict[str, Any]:
        """Intelligently analyze the file structure"""
        analysis = {
            'file_size': len(self.data),
            'header_analysis': {},
            'section_analysis': [],
            'encoding_hints': [],
            'compression_hints': []
        }

        # Analyze header patterns
        header = self.data[:1000]
        analysis['header_analysis'] = {
            'printable_ratio': sum(1 for b in header if 32 <= b <= 126) / len(header) if len(header) else 0,
            'null_ratio': header.count(b'\x00') / len(header) if len(header) else 0,
            'common_bytes': [b for b, count in sorted([(b, header.count(b)) for b in set(header)], key=lambda x: x[1], reverse=True)[:10]]
        }

        # Look for section markers
        section_markers = [b'hsin', b'DSIN', b'RIFF', b'FORM', b'data', b'INFO']
        for marker in section_markers:
            positions = []
            pos = 0
            while True:
                pos = self.data.find(marker, pos)
                if pos == -1:
                    break
                positions.append(pos)
                pos += 1

            if positions:
                analysis['section_analysis'].append({
                    'marker': marker.decode('ascii', errors='ignore'),
                    'positions': positions,
                    'count': len(positions)
                })

        # Look for encoding hints
        if b'\xff\xfe' in self.data:  # UTF-16LE BOM
            analysis['encoding_hints'].append('UTF-16LE')
        if b'\xfe\xff' in self.data:  # UTF-16BE BOM
            analysis['encoding_hints'].append('UTF-16BE')
        if b'\xef\xbb\xbf' in self.data:  # UTF-8 BOM
            analysis['encoding_hints'].append('UTF-8')

        # Look for compression hints
        if b'\x78\x9c' in self.data:  # zlib
            analysis['compression_hints'].append('zlib')
        if b'\x1f\x8b' in self.data:  # gzip
            analysis['compression_hints'].append('gzip')
        if b'\x42\x5a' in self.data:  # bzip2
            analysis['compression_hints'].append('bzip2')

        return analysis

    def smart_string_extraction(self, target_patterns: List[str] = None) -> List[Dict[str, Any]]:
        """Intelligently extract strings based on file analysis"""
        if target_patterns is None:
            target_patterns = ['aquamarine', 'wav', 'wave', 'audio', 'sample']

        strings = []

        # Try different string extraction strategies
        strategies = [
            ('null_terminated', self._extract_null_terminated_strings),
            ('length_prefixed', self._extract_length_prefixed_strings),
            ('utf16_strings', self._extract_utf16_strings),
            ('utf16le_strings', self._extract_utf16le_strings),
            ('utf16be_strings', self._extract_utf16be_strings),
            ('printable_sequences', self._extract_printable_sequences)
        ]

        for strategy_name, strategy_func in strategies:
            try:
                strategy_strings = strategy_func(target_patterns)
                strings.extend(strategy_strings)
                print(f"[+] {strategy_name}: Found {len(strategy_strings)} relevant strings")
            except Exception as e:
                print(f"[-] {strategy_name}: Error - {e}")

        return strings

    def _extract_null_terminated_strings(self, target_patterns: List[str]) -> List[Dict[str, Any]]:
        """Extract null-terminated strings"""
        strings = []
        current_string = ""
        start_idx = 0

        for i, byte in enumerate(self.data):
            if 32 <= byte <= 126:  # Printable ASCII
                if current_string == "":
                    start_idx = i
                current_string += chr(byte)
            else:
                if len(current_string) >= 3:
                    if any(pattern in current_string.lower() for pattern in target_patterns):
                        strings.append({
                            'string': current_string,
                            'position': start_idx,
                            'method': 'null_terminated',
                            'context': self._get_context(start_idx, 50)
                        })
                current_string = ""

        return strings

    def _extract_length_prefixed_strings(self, target_patterns: List[str]) -> List[Dict[str, Any]]:
        """Extract length-prefixed strings"""
        strings = []

        for i in range(len(self.data) - 4):
            try:
                # Try different length prefix formats
                length_formats = [
                    ('uint8', struct.unpack('<B', self.data[i:i + 1])[0]),
                    ('uint16_le', struct.unpack('<H', self.data[i:i + 2])[0]),
                    ('uint16_be', struct.unpack('>H', self.data[i:i + 2])[0]),
                    ('uint32_le', struct.unpack('<I', self.data[i:i + 4])[0]),
                    ('uint32_be', struct.unpack('>I', self.data[i:i + 4])[0])
                ]

                for format_name, length in length_formats:
                    # Decide offset for string read depending on assumed prefix size
                    offset = 1 if format_name == 'uint8' else 2 if 'uint16' in format_name else 4
                    if 3 <= length <= 200 and i + offset + length <= len(self.data):
                        string_data = self.data[i + offset:i + offset + length]
                        try:
                            string = string_data.decode('ascii', errors='ignore')
                            if any(pattern in string.lower() for pattern in target_patterns):
                                strings.append({
                                    'string': string,
                                    'position': i,
                                    'method': f'length_prefixed_{format_name}',
                                    'context': self._get_context(i, 50)
                                })
                        except:
                            pass
            except:
                pass

        return strings

    def _extract_utf16_strings(self, target_patterns: List[str]) -> List[Dict[str, Any]]:
        """Extract UTF-16 strings"""
        strings = []

        for i in range(0, len(self.data) - 4, 2):
            try:
                # Try to decode as UTF-16
                chunk = self.data[i:i + 200]  # look a bit further
                string = chunk.decode('utf-16', errors='ignore')
                if any(pattern in string.lower() for pattern in target_patterns):
                    strings.append({
                        'string': string,
                        'position': i,
                        'method': 'utf16',
                        'context': self._get_context(i, 50)
                    })
            except:
                pass

        return strings

    def _extract_utf16le_strings(self, target_patterns: List[str]) -> List[Dict[str, Any]]:
        """Extract UTF-16LE strings"""
        strings = []

        for i in range(0, len(self.data) - 4, 2):
            try:
                chunk = self.data[i:i + 200]
                string = chunk.decode('utf-16le', errors='ignore')
                if any(pattern in string.lower() for pattern in target_patterns):
                    strings.append({
                        'string': string,
                        'position': i,
                        'method': 'utf16le',
                        'context': self._get_context(i, 50)
                    })
            except:
                pass

        return strings

    def _extract_utf16be_strings(self, target_patterns: List[str]) -> List[Dict[str, Any]]:
        """Extract UTF-16BE strings"""
        strings = []

        for i in range(0, len(self.data) - 4, 2):
            try:
                chunk = self.data[i:i + 200]
                string = chunk.decode('utf-16be', errors='ignore')
                if any(pattern in string.lower() for pattern in target_patterns):
                    strings.append({
                        'string': string,
                        'position': i,
                        'method': 'utf16be',
                        'context': self._get_context(i, 50)
                    })
            except:
                pass

        return strings

    def _extract_printable_sequences(self, target_patterns: List[str]) -> List[Dict[str, Any]]:
        """Extract sequences of printable characters"""
        strings = []
        current_string = ""
        start_idx = 0

        for i, byte in enumerate(self.data):
            if 32 <= byte <= 126:  # Printable ASCII
                if current_string == "":
                    start_idx = i
                current_string += chr(byte)
            else:
                if len(current_string) >= 4:
                    if any(pattern in current_string.lower() for pattern in target_patterns):
                        strings.append({
                            'string': current_string,
                            'position': start_idx,
                            'method': 'printable_sequence',
                            'context': self._get_context(start_idx, 50)
                        })
                current_string = ""

        return strings

    def _get_context(self, position: int, context_size: int) -> str:
        """Get context around a position (hex-encoded for safe storage)"""
        start = max(0, position - context_size)
        end = min(len(self.data), position + context_size)
        context = self.data[start:end]
        return context.hex()

    def intelligent_decompression(self, target_strings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Intelligently try decompression based on found strings

        Returns a list of dicts where each dict may include:
          - original_string: the string that triggered the attempt
          - method: 'zlib' or 'base64'
          - position: start position used for attempt
          - decompressed: short ascii preview (first 200 chars)
          - raw_bytes: the full bytes result (when available)
          - context: hex context
        """
        results = []

        for string_info in target_strings:
            position = string_info['position']

            # Try decompression around the found string
            for offset in range(-100, 101, 10):
                start_pos = max(0, position + offset)
                end_pos = min(len(self.data), start_pos + 1000)

                chunk = self.data[start_pos:end_pos]

                # Try zlib decompression (bytes -> bytes)
                try:
                    decompressed_bytes = zlib.decompress(chunk)
                    # prepare ascii preview but keep raw bytes
                    decoded_preview = decompressed_bytes.decode('ascii', errors='ignore')
                    if any(pattern in decoded_preview.lower() for pattern in ['wav', 'aquamarine', 'audio']):
                        results.append({
                            'original_string': string_info['string'],
                            'decompressed': decoded_preview[:200],
                            'raw_bytes': decompressed_bytes,
                            'method': 'zlib',
                            'position': start_pos,
                            'context': self._get_context(start_pos, 50)
                        })
                    else:
                        # still store decompressions even if preview didn't match
                        results.append({
                            'original_string': string_info['string'],
                            'decompressed': decoded_preview[:200],
                            'raw_bytes': decompressed_bytes,
                            'method': 'zlib',
                            'position': start_pos,
                            'context': self._get_context(start_pos, 50)
                        })
                except Exception:
                    pass

                # Try base64 decoding (may raise)
                try:
                    decoded_bytes = base64.b64decode(chunk)
                    ascii_decoded = decoded_bytes.decode('ascii', errors='ignore')
                    if any(pattern in ascii_decoded.lower() for pattern in ['wav', 'aquamarine', 'audio']):
                        results.append({
                            'original_string': string_info['string'],
                            'decompressed': ascii_decoded[:200],
                            'raw_bytes': decoded_bytes,
                            'method': 'base64',
                            'position': start_pos,
                            'context': self._get_context(start_pos, 50)
                        })
                    else:
                        results.append({
                            'original_string': string_info['string'],
                            'decompressed': ascii_decoded[:200],
                            'raw_bytes': decoded_bytes,
                            'method': 'base64',
                            'position': start_pos,
                            'context': self._get_context(start_pos, 50)
                        })
                except Exception:
                    pass

        return results

    def pattern_based_decoding(self) -> List[Dict[str, Any]]:
        """Use pattern-based decoding based on known file structures"""
        results = []

        # Look for common patterns that might indicate WAV file references
        patterns = [
            (rb'[A-Za-z0-9_\-\./\\]+\.wav', 'wav_file_path'),
            (rb'[A-Za-z0-9_\-\./\\]+\.WAV', 'wav_file_path_upper'),
            (rb'aquamarine[^\\x00]*\.wav', 'aquamarine_wav'),
            (rb'[A-Za-z0-9_\-\./\\]+aquamarine[^\\x00]*', 'aquamarine_reference'),
            (rb'RIFF[^\\x00]{4}WAVE', 'wav_header'),
            (rb'data[^\\x00]{4}', 'wav_data')
        ]

        for pattern, pattern_name in patterns:
            matches = re.finditer(pattern, self.data, re.IGNORECASE)
            for match in matches:
                try:
                    matched_string = match.group(0).decode('ascii', errors='ignore')
                    results.append({
                        'pattern': pattern_name,
                        'string': matched_string,
                        'position': match.start(),
                        'context': self._get_context(match.start(), 100)
                    })
                except:
                    pass

        return results

    def context_aware_decoding(self, target_strings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use context-aware decoding to find related strings"""
        results = []

        for string_info in target_strings:
            position = string_info['position']

            # Look for strings before and after the target string
            for offset in range(-200, 201, 10):
                check_pos = position + offset
                if 0 <= check_pos < len(self.data) - 10:

                    # Try to extract a string at this position
                    chunk = self.data[check_pos:check_pos + 200]

                    # Try different encodings
                    for encoding in ['ascii', 'utf-8', 'utf-16', 'utf-16le', 'utf-16be']:
                        try:
                            decoded = chunk.decode(encoding, errors='ignore')
                            if any(pattern in decoded.lower() for pattern in ['wav', 'audio', 'sample', 'file', 'path']):
                                results.append({
                                    'related_to': string_info['string'],
                                    'found_string': decoded,
                                    'position': check_pos,
                                    'encoding': encoding,
                                    'context': self._get_context(check_pos, 50)
                                })
                        except:
                            pass

        return results

    def _save_raw_copy(self, output_dir: str):
        """Save a raw copy of the original file for reference."""
        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        raw_copy_path = os.path.join(output_dir, f"{base_name}_original.bin")
        with open(raw_copy_path, 'wb') as f:
            f.write(self.data)
        print(f"[+] Saved raw copy: {raw_copy_path}")
        return raw_copy_path

    def _extract_riff_chunks(self, output_dir: str) -> List[str]:
        """Extract RIFF chunks (WAV) from the raw data using RIFF size field.

        RIFF header layout:
          0..3: 'RIFF'
          4..7: uint32 little-endian = chunk size (file size - 8)
        """
        saved_files = []
        pos = 0
        found = 0
        while True:
            pos = self.data.find(b'RIFF', pos)
            if pos == -1:
                break
            # Check that we have at least 8 bytes for header
            if pos + 8 > len(self.data):
                break
            try:
                size = struct.unpack_from('<I', self.data, pos + 4)[0]
                total_size = 8 + size  # RIFF chunk size is file_size - 8
                if total_size <= 8 or pos + total_size > len(self.data):
                    # If the size is implausible, attempt to find a safer end by searching for next 'RIFF'
                    next_pos = self.data.find(b'RIFF', pos + 4)
                    end = next_pos if next_pos != -1 else min(pos + 2000000, len(self.data))
                else:
                    end = pos + total_size

                chunk = self.data[pos:end]
                # save chunk as wav
                found += 1
                out_name = os.path.join(output_dir, f"extracted_riff_{found}.wav")
                with open(out_name, 'wb') as wf:
                    wf.write(chunk)
                saved_files.append(out_name)
                print(f"[+] Extracted RIFF/WAVE at pos {pos} -> {out_name} (size ~{len(chunk)})")
            except Exception as e:
                print(f"[-] Error extracting RIFF at pos {pos}: {e}")
            pos += 4
        if not saved_files:
            print("[*] No RIFF/WAVE chunks found with RIFF header parsing.")
        return saved_files

    def _guess_extension_and_save(self, output_dir: str, file_bytes: bytes, prefix: str, index: int) -> str:
        """Guess a sensible extension for bytes and save to disk."""
        # Detect WAV
        if file_bytes.startswith(b'RIFF') and b'WAVE' in file_bytes[:12]:
            ext = 'wav'
        else:
            # Heuristic: if printable fraction is high, save as .txt
            printable = sum(1 for b in file_bytes if 32 <= b <= 126)
            ratio = printable / max(1, len(file_bytes))
            if ratio > 0.6 and len(file_bytes) < 200000:
                ext = 'txt'
            else:
                ext = 'bin'

        out_path = os.path.join(output_dir, f"{prefix}_{index}.{ext}")
        mode = 'w' if ext == 'txt' else 'wb'
        with open(out_path, mode, encoding='utf-8' if ext == 'txt' else None) as f:
            if ext == 'txt':
                try:
                    f.write(file_bytes.decode('utf-8', errors='ignore'))
                except:
                    f.write(binascii.hexlify(file_bytes).decode('ascii'))
            else:
                f.write(file_bytes)
        return out_path

    def _save_decompression_outputs(self, output_dir: str, decompression_results: List[Dict[str, Any]]) -> List[str]:
        """Save raw decompressed bytes found by intelligent_decompression to separate files."""
        saved = []
        for i, info in enumerate(decompression_results, 1):
            raw = info.get('raw_bytes')
            if raw:
                try:
                    path = self._guess_extension_and_save(output_dir, raw, "decompressed", i)
                    saved.append(path)
                    print(f"[+] Saved decompressed output ({info.get('method')}) -> {path}")
                except Exception as e:
                    print(f"[-] Failed to save decompressed result #{i}: {e}")
            else:
                # If there are no raw_bytes but have a textual preview, save that as txt
                preview = info.get('decompressed')
                if preview:
                    ppath = os.path.join(output_dir, f"decompressed_preview_{i}.txt")
                    with open(ppath, 'w', encoding='utf-8') as pf:
                        pf.write(preview)
                    saved.append(ppath)
        if not saved:
            print("[*] No decompressed results saved.")
        return saved

    def parse(self):
        """Main intelligent parsing function"""
        print(f"[+] Starting intelligent decoding analysis...")

        # Load file
        self.load_file()

        # Analyze file structure
        print("[+] Analyzing file structure...")
        structure_analysis = self.analyze_file_structure()
        print(f"[+] File analysis complete:")
        print(f"    - Size: {structure_analysis['file_size']} bytes")
        print(f"    - Encoding hints: {structure_analysis['encoding_hints']}")
        print(f"    - Compression hints: {structure_analysis['compression_hints']}")
        print(f"    - Sections found: {len(structure_analysis['section_analysis'])}")

        # Smart string extraction
        print("[+] Performing smart string extraction...")
        target_strings = self.smart_string_extraction(['aquamarine', 'wav', 'wave', 'audio', 'sample'])
        print(f"[+] Found {len(target_strings)} target strings")

        # Intelligent decompression
        print("[+] Performing intelligent decompression...")
        decompression_results = self.intelligent_decompression(target_strings)
        print(f"[+] Found {len(decompression_results)} decompression results")

        # Pattern-based decoding
        print("[+] Performing pattern-based decoding...")
        pattern_results = self.pattern_based_decoding()
        print(f"[+] Found {len(pattern_results)} pattern results")

        # Context-aware decoding
        print("[+] Performing context-aware decoding...")
        context_results = self.context_aware_decoding(target_strings)
        print(f"[+] Found {len(context_results)} context results")

        # Compile all results
        all_results = {
            'structure_analysis': structure_analysis,
            'target_strings': target_strings,
            'decompression_results': decompression_results,
            'pattern_results': pattern_results,
            'context_results': context_results
        }

        # Save results (and extracted/decompiled files)
        self.save_results(all_results)

        return all_results

    def save_results(self, results: Dict[str, Any]):
        """Save intelligent decoding results and export decompiled/extracted files"""
        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        output_parent = "out/battery"
        output_dir = os.path.join(output_parent, base_name)
        os.makedirs(output_dir, exist_ok=True)

        # 1) Save a raw copy of the original file
        raw_copy_path = self._save_raw_copy(output_dir)

        # 2) Save summary JSON
        summary_file = os.path.join(output_dir, f"{base_name}_intelligent_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'file': self.file_path,
                'file_size': len(self.data),
                'target_strings_count': len(results['target_strings']),
                'decompression_results_count': len(results['decompression_results']),
                'pattern_results_count': len(results['pattern_results']),
                'context_results_count': len(results['context_results']),
                'structure_analysis': results['structure_analysis']
            }, f, indent=2, ensure_ascii=False)
        print(f"[+] Saved summary: {summary_file}")

        # 3) Save detailed text results
        results_file = os.path.join(output_dir, f"{base_name}_intelligent_results.txt")
        with open(results_file, 'w', encoding='utf-8') as f:
            f.write(f"Intelligent Decoding Analysis Results\n")
            f.write(f"File: {self.file_path}\n")
            f.write(f"Size: {len(self.data)} bytes\n\n")

            f.write("=== TARGET STRINGS ===\n")
            for i, string_info in enumerate(results['target_strings'], 1):
                f.write(f"{i:3d}. [{string_info['method']}] {string_info['string']}\n")
                f.write(f"     Position: {string_info['position']}\n")
                f.write(f"     Context (hex): {string_info['context'][:200]}...\n\n")

            f.write("=== DECOMPRESSION RESULTS ===\n")
            for i, decomp_info in enumerate(results['decompression_results'], 1):
                f.write(f"{i:3d}. [{decomp_info['method']}] {decomp_info.get('decompressed', '')}\n")
                f.write(f"     Original: {decomp_info.get('original_string')}\n")
                f.write(f"     Position: {decomp_info.get('position')}\n\n")

            f.write("=== PATTERN RESULTS ===\n")
            for i, pattern_info in enumerate(results['pattern_results'], 1):
                f.write(f"{i:3d}. [{pattern_info['pattern']}] {pattern_info['string']}\n")
                f.write(f"     Position: {pattern_info['position']}\n")
                f.write(f"     Context (hex): {pattern_info['context'][:200]}...\n\n")

            f.write("=== CONTEXT RESULTS ===\n")
            for i, context_info in enumerate(results['context_results'], 1):
                f.write(f"{i:3d}. [{context_info.get('encoding', 'unknown')}] {context_info['found_string']}\n")
                f.write(f"     Related to: {context_info.get('related_to')}\n")
                f.write(f"     Position: {context_info.get('position')}\n\n")

        print(f"[+] Saved details: {results_file}")

        # 4) Save each target string into its own numbered text file (useful if you want to copy/paste)
        tstrings_dir = os.path.join(output_dir, "target_strings")
        os.makedirs(tstrings_dir, exist_ok=True)
        for i, si in enumerate(results['target_strings'], 1):
            tpath = os.path.join(tstrings_dir, f"target_string_{i}.txt")
            with open(tpath, 'w', encoding='utf-8') as tf:
                tf.write(f"Method: {si.get('method')}\n")
                tf.write(f"Position: {si.get('position')}\n")
                tf.write("String:\n")
                tf.write(si.get('string', ''))
                tf.write("\n\nContext (hex):\n")
                tf.write(si.get('context', ''))
        print(f"[+] Saved {len(results['target_strings'])} target strings to: {tstrings_dir}")

        # 5) Save pattern results as JSON + per-file text
        pattern_path = os.path.join(output_dir, f"{base_name}_pattern_results.json")
        with open(pattern_path, 'w', encoding='utf-8') as pf:
            json.dump(results['pattern_results'], pf, indent=2, ensure_ascii=False)
        print(f"[+] Saved pattern results JSON: {pattern_path}")

        # Also save each pattern result as a short text file
        patterns_dir = os.path.join(output_dir, "pattern_matches")
        os.makedirs(patterns_dir, exist_ok=True)
        for i, pr in enumerate(results['pattern_results'], 1):
            pfile = os.path.join(patterns_dir, f"pattern_{i}.txt")
            with open(pfile, 'w', encoding='utf-8') as ppf:
                ppf.write(json.dumps(pr, indent=2, ensure_ascii=False))
        print(f"[+] Saved {len(results['pattern_results'])} pattern matches into {patterns_dir}")

        # 6) Save context results as JSON
        context_path = os.path.join(output_dir, f"{base_name}_context_results.json")
        with open(context_path, 'w', encoding='utf-8') as cf:
            json.dump(results['context_results'], cf, indent=2, ensure_ascii=False)
        print(f"[+] Saved context results JSON: {context_path}")

        # 7) Attempt to extract RIFF/WAVE chunks from the raw data
        riff_files = self._extract_riff_chunks(output_dir)

        # 8) Save decompression outputs (raw bytes) to disk
        decompressed_saved = self._save_decompression_outputs(output_dir, results['decompression_results'])

        # Final report
        print(f"[+] Export complete. Directory: {output_dir}")
        print(f"    - Raw copy: {raw_copy_path}")
        print(f"    - Summary JSON: {summary_file}")
        print(f"    - Details: {results_file}")
        if riff_files:
            print(f"    - Extracted RIFF/WAV files: {len(riff_files)} (saved in {output_dir})")
        if decompressed_saved:
            print(f"    - Decompressed outputs saved: {len(decompressed_saved)}")
        print("    - Additional files: target_strings/, pattern_matches/, *_pattern_results.json, *_context_results.json")

def main():
    import sys

    if len(sys.argv) != 2:
        print("Usage: python intelligent_decoder.py <nbkt_file>")
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        sys.exit(1)

    decoder = IntelligentDecoder(file_path)
    results = decoder.parse()

    print(f"\n[+] Intelligent decoding analysis complete!")
    print(f"    File: {file_path}")
    print(f"    Size: {len(decoder.data)} bytes")
    print(f"    Target strings: {len(results['target_strings'])}")
    print(f"    Decompression results: {len(results['decompression_results'])}")
    print(f"    Pattern results: {len(results['pattern_results'])}")
    print(f"    Context results: {len(results['context_results'])}")


if __name__ == "__main__":
    main()
