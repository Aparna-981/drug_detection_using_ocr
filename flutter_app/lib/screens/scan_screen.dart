import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import 'package:image_cropper/image_cropper.dart';
import '../services/api_service.dart';
import 'result_screen.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  File? _image;
  Uint8List? _imageBytes;

  bool _isProcessing = false;
  String _statusMsg = '';

  final _picker = ImagePicker();

  // ✅ PICK IMAGE (WORKS BOTH WEB + MOBILE)
  Future<void> _pick(ImageSource source) async {
    setState(() {
      _statusMsg = 'Opening ${source == ImageSource.camera ? "camera" : "gallery"}...';
    });

    try {
      final xf = await _picker.pickImage(
        source: source,
        imageQuality: 92,
        maxWidth: 2048,
      );

      if (xf == null) {
        setState(() => _statusMsg = '');
        return;
      }

      setState(() => _statusMsg = 'Loading cropper...');

      final croppedFile = await ImageCropper().cropImage(
        sourcePath: xf.path,
        uiSettings: [
          AndroidUiSettings(
            toolbarTitle: 'Crop Medicine Image',
            toolbarColor: const Color(0xFF1565C0),
            toolbarWidgetColor: Colors.white,
            initAspectRatio: CropAspectRatioPreset.original,
            lockAspectRatio: false,
          ),
          IOSUiSettings(
            title: 'Crop Medicine Image',
          ),
          WebUiSettings(
            context: context,
            presentStyle: WebPresentStyle.page, // 🚀 Standard full-screen style (Top Buttons)
            size: const CropperSize(
              width: 1024, // High resolution for better OCR
              height: 768,
            ),
          ),
        ],
      );

      debugPrint('Cropper returned file: $croppedFile');

      if (croppedFile != null) {
        if (kIsWeb) {
          final bytes = await croppedFile.readAsBytes();
          debugPrint('Read ${bytes.length} bytes from cropped file');
          setState(() {
            _imageBytes = bytes;
            _image = null;
            _statusMsg = '';
          });
        } else {
          setState(() {
            _image = File(croppedFile.path);
            _imageBytes = null;
            _statusMsg = '';
          });
        }
      } else {
        setState(() => _statusMsg = '');
      }
    } catch (e) {
      debugPrint('Error picking/cropping: $e');
      setState(() => _statusMsg = 'Error picking image.');
    }
  }

  // ✅ ANALYSE IMAGE
  Future<void> _analyse() async {
    if (_image == null && _imageBytes == null) return;

    setState(() {
      _isProcessing = true;
      _statusMsg = 'Preprocessing image…';
    });

    await Future.delayed(const Duration(milliseconds: 100));

    setState(() {
      _statusMsg = 'Running PaddleOCR — this may take 10–30 s…';
    });

    try {
      final data = await ApiService.scanImage(
        kIsWeb ? _imageBytes! : _image!,
      );

      if (!mounted) return;

      if (data.containsKey('error')) {
        _showError(data['error'] as String);
      } else {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => ResultScreen(data: data),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isProcessing = false;
          _statusMsg = '';
        });
      }
    }
  }

  // ✅ ERROR DIALOG
  void _showError(String msg) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.error_outline, color: Colors.red),
            SizedBox(width: 8),
            Text('Error'),
          ],
        ),
        content: Text(msg),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1565C0),
        foregroundColor: Colors.white,
        title: const Text(
          'Scan Medicine',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            // 🔹 TIP BOX
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(13),
              decoration: BoxDecoration(
                color: const Color(0xFFE3F2FD),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFF90CAF9)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.tips_and_updates,
                      color: Color(0xFF1565C0), size: 20),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Tip: Place the package on a flat surface in good light.',
                      style: TextStyle(
                          fontSize: 12, color: Color(0xFF1565C0)),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // 🔹 IMAGE PREVIEW (FIXED)
            GestureDetector(
              onTap: () => _pick(ImageSource.camera),
              child: Container(
                width: double.infinity,
                height: 270,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(
                    color: (_image != null || _imageBytes != null)
                        ? const Color(0xFF1565C0)
                        : Colors.grey[300]!,
                    width: 2,
                  ),
                ),
                child: (_image != null || _imageBytes != null)
                    ? ClipRRect(
                        borderRadius: BorderRadius.circular(16),
                        child: kIsWeb
                            ? Image.memory(_imageBytes!,
                                fit: BoxFit.contain)
                            : Image.file(_image!,
                                fit: BoxFit.contain),
                      )
                    : Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.add_a_photo_outlined,
                              size: 60, color: Colors.grey[400]),
                          const SizedBox(height: 10),
                          Text('Tap to open camera',
                              style: TextStyle(
                                  fontSize: 15,
                                  color: Colors.grey[500])),
                          Text('or use buttons below',
                              style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey[400])),
                        ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // 🔹 ACTION AREA (Changes based on image presence)
            if (_image != null || _imageBytes != null) ...[
              const SizedBox(height: 10),
              // 🚀 PRIMARY UPLOAD BUTTON
              SizedBox(
                width: double.infinity,
                height: 60,
                child: ElevatedButton.icon(
                  onPressed: _isProcessing ? null : _analyse,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1565C0),
                    foregroundColor: Colors.white,
                    elevation: 6,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16)),
                  ),
                  icon: _isProcessing
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(
                              color: Colors.white, strokeWidth: 3),
                        )
                      : const Icon(Icons.cloud_upload, size: 28),
                  label: Text(
                    _isProcessing ? 'SCANNING...' : 'UPLOAD & SCAN NOW',
                    style: const TextStyle(
                        fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
              const SizedBox(height: 15),
              TextButton.icon(
                onPressed: _isProcessing ? null : () => _pick(ImageSource.camera),
                icon: const Icon(Icons.refresh, color: Colors.grey),
                label: const Text('Retake or change photo',
                    style: TextStyle(color: Colors.grey)),
              ),
            ] else ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _pick(ImageSource.camera),
                      icon: const Icon(Icons.camera_alt),
                      label: const Text('Camera'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _pick(ImageSource.gallery),
                      icon: const Icon(Icons.photo_library),
                      label: const Text('Gallery'),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 12),

            // 🔹 STATUS
            if (_isProcessing && _statusMsg.isNotEmpty) ...[
              const SizedBox(height: 14),
              Text(
                _statusMsg,
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}