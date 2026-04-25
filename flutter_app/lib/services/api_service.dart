// ignore_for_file: constant_identifier_names

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data'; // ✅ IMPORTANT for web
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

// ─────────────────────────────────────────────────────────────
// ⚠️ SET YOUR BACKEND URL HERE
// ─────────────────────────────────────────────────────────────
const String BASE_URL = "http://localhost:8000";

class ApiService {
  // ── Health check ────────────────────────────────────────
  static Future<Map<String, dynamic>> checkHealth() async {
    try {
      final res = await http
          .get(Uri.parse('$BASE_URL/health'))
          .timeout(const Duration(seconds: 6));

      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
      return {'status': 'error', 'message': 'Server returned ${res.statusCode}'};
    } catch (_) {
      return {'status': 'offline'};
    }
  }

  // ── Scan medicine image (FIXED FOR WEB + MOBILE) ────────
  static Future<Map<String, dynamic>> scanImage(dynamic image) async {
    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$BASE_URL/scan'),
      );

      // ✅ MOBILE (File)
      if (image is File) {
        final ext = image.path.split('.').last.toLowerCase();
        final mime = ext == 'png' ? 'png' : 'jpeg';

        request.files.add(await http.MultipartFile.fromPath(
          'file',
          image.path,
          contentType: MediaType('image', mime),
        ));
      }

      // ✅ WEB (Uint8List)
      else if (image is Uint8List) {
        request.files.add(http.MultipartFile.fromBytes(
          'file',
          image,
          filename: 'image.jpg',
          contentType: MediaType('image', 'jpeg'),
        ));
      }

      final streamed = await request.send().timeout(
        const Duration(seconds: 90),
      );

      final res = await http.Response.fromStream(streamed);

      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }

      try {
        final err = jsonDecode(res.body);
        return {'error': err['detail'] ?? 'Server error ${res.statusCode}'};
      } catch (_) {
        return {'error': 'Server error: ${res.statusCode}'};
      }
    } on SocketException {
      return {
        'error':
            'Cannot connect to server.\nMake sure the Python backend is running.'
      };
    } on http.ClientException catch (e) {
      return {'error': 'Connection error: ${e.message}'};
    } catch (e) {
      return {'error': 'Error: $e'};
    }
  }

  // ── Manual drug name check ───────────────────────────────
  static Future<Map<String, dynamic>> checkManual({
    required String drugName,
    String batchNo = '',
    String expDate = '',
  }) async {
    try {
      final res = await http
          .post(
            Uri.parse('$BASE_URL/check-manual'),
            body: {
              'drug_name': drugName,
              'batch_no': batchNo,
              'exp_date': expDate,
            },
          )
          .timeout(const Duration(seconds: 20));

      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }

      try {
        final err = jsonDecode(res.body);
        return {'error': err['detail'] ?? 'Server error ${res.statusCode}'};
      } catch (_) {
        return {'error': 'Server error: ${res.statusCode}'};
      }
    } on SocketException {
      return {'error': 'Cannot connect to server.'};
    } catch (e) {
      return {'error': 'Error: $e'};
    }
  }

  // ── Upload new NSQ dataset (Supports PDF + EXCEL) ──────────
  static Future<Map<String, dynamic>> uploadDataset(dynamic file, String fileName) async {
    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$BASE_URL/upload-dataset'),
      );

      final ext = fileName.split('.').last.toLowerCase();
      MediaType contentType;
      
      if (ext == 'xlsx') {
        contentType = MediaType('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      } else if (ext == 'xls') {
        contentType = MediaType('application', 'vnd.ms-excel');
      } else {
        contentType = MediaType('application', 'pdf');
      }

      // ✅ MOBILE (File)
      if (file is File) {
        request.files.add(await http.MultipartFile.fromPath(
          'file',
          file.path,
          filename: fileName,
          contentType: contentType,
        ));
      }
      // ✅ WEB (Uint8List)
      else if (file is Uint8List) {
        request.files.add(http.MultipartFile.fromBytes(
          'file',
          file,
          filename: fileName,
          contentType: contentType,
        ));
      }

      final streamed = await request.send().timeout(
        const Duration(seconds: 120),
      );

      final res = await http.Response.fromStream(streamed);

      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }

      return {'error': 'Upload failed: ${res.statusCode}'};
    } on SocketException {
      return {'error': 'Cannot connect to server.'};
    } catch (e) {
      return {'error': 'Upload error: $e'};
    }
  }

  // ── Get dataset info ─────────────────────────────────────
  static Future<Map<String, dynamic>> getDatasetInfo() async {
    try {
      final res = await http
          .get(Uri.parse('$BASE_URL/dataset-info'))
          .timeout(const Duration(seconds: 10));

      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }

      return {'error': 'Failed to fetch dataset info'};
    } catch (e) {
      return {'error': '$e'};
    }
  }

  // ── Registration ─────────────────────────────────────────
  static Future<Map<String, dynamic>> register(String username, String password) async {
    try {
      final res = await http.post(
        Uri.parse('$BASE_URL/register'),
        body: {'username': username, 'password': password},
      ).timeout(const Duration(seconds: 10));

      final data = jsonDecode(res.body);
      if (res.statusCode == 200) return data;
      return {'error': data['detail'] ?? 'Registration failed'};
    } catch (e) {
      return {'error': 'Cannot connect to server.'};
    }
  }

  // ── Login ──────────────────────────────────────────────
  static Future<Map<String, dynamic>> login(String username, String password) async {
    try {
      final res = await http.post(
        Uri.parse('$BASE_URL/login'),
        body: {'username': username, 'password': password},
      ).timeout(const Duration(seconds: 10));

      final data = jsonDecode(res.body);
      if (res.statusCode == 200) return data;
      return {'error': data['detail'] ?? 'Login failed'};
    } catch (e) {
      return {'error': 'Cannot connect to server.'};
    }
  }

  // ── Admin: List Pending Users ────────────────────────────
  static Future<List<dynamic>> getPendingUsers() async {
    try {
      final res = await http.get(Uri.parse('$BASE_URL/admin/users/pending'))
          .timeout(const Duration(seconds: 10));
      if (res.statusCode == 200) return jsonDecode(res.body);
      return [];
    } catch (_) {
      return [];
    }
  }

  // ── Admin: Get All Users ─────────────────────────────────
  static Future<List<dynamic>> getAllUsers() async {
    try {
      final res = await http.get(Uri.parse('$BASE_URL/admin/users'))
          .timeout(const Duration(seconds: 10));
      if (res.statusCode == 200) return jsonDecode(res.body);
      return [];
    } catch (_) {
      return [];
    }
  }

  // ── Admin: Approve User ──────────────────────────────────
  static Future<bool> approveUser(int userId) async {
    try {
      final res = await http.post(Uri.parse('$BASE_URL/admin/users/approve/$userId'))
          .timeout(const Duration(seconds: 10));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ── Admin: Reject User ───────────────────────────────────
  static Future<bool> rejectUser(int userId) async {
    try {
      final res = await http.post(Uri.parse('$BASE_URL/admin/users/reject/$userId'))
          .timeout(const Duration(seconds: 10));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ── Admin: Search Drugs ──────────────────────────────────
  static Future<List<dynamic>> searchDrugs(String query) async {
    try {
      final res = await http.get(Uri.parse('$BASE_URL/admin/drugs/search?q=$query'))
          .timeout(const Duration(seconds: 10));
      if (res.statusCode == 200) return jsonDecode(res.body);
      return [];
    } catch (_) {
      return [];
    }
  }
}