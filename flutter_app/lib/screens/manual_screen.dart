import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'result_screen.dart';

class ManualScreen extends StatefulWidget {
  const ManualScreen({super.key});

  @override
  State<ManualScreen> createState() => _ManualScreenState();
}

class _ManualScreenState extends State<ManualScreen> {
  final _formKey       = GlobalKey<FormState>();
  final _nameCtrl      = TextEditingController();
  final _batchCtrl     = TextEditingController();
  final _expCtrl       = TextEditingController();
  bool _loading        = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _batchCtrl.dispose();
    _expCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    // Capture values before clearing
    final drugName = _nameCtrl.text.trim();
    final batchNo  = _batchCtrl.text.trim();
    final expDate  = _expCtrl.text.trim();

    setState(() => _loading = true);

    try {
      final result = await ApiService.checkManual(
        drugName: drugName,
        batchNo:  batchNo,
        expDate:  expDate,
      );

      if (!mounted) return;

      if (result.containsKey('error')) {
        _showError(result['error'] as String);
      } else {
        // ✅ Clear the form so next search starts fresh
        _nameCtrl.clear();
        _batchCtrl.clear();
        _expCtrl.clear();

        // ✅ pushReplacement so Back goes to Home, not old filled form
        Navigator.pushReplacement(context,
            MaterialPageRoute(builder: (_) => ResultScreen(data: result)));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _showError(String msg) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Row(children: [
          Icon(Icons.error_outline, color: Colors.red),
          SizedBox(width: 8),
          Text('Error'),
        ]),
        content: Text(msg),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('OK')),
        ],
      ),
    );
  }

  InputDecoration _fieldDecor(String hint, IconData icon) => InputDecoration(
        hintText: hint,
        prefixIcon: Icon(icon),
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide.none),
        enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: Colors.grey[300]!)),
        focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide:
                const BorderSide(color: Color(0xFF2E7D32), width: 2)),
      );

  @override
  Widget build(BuildContext context) {
    const examples = [
      'Pantoprazole',
      'Gentamicin',
      'Calcium Carbonate',
      'Nitrazepam',
      'Domperidone',
      'Alprazolam',
    ];

    return Scaffold(
      backgroundColor: const Color(0xFFF0F4FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFF2E7D32),
        foregroundColor: Colors.white,
        title: const Text('Manual Drug Check',
            style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Info ──────────────────────────────────────
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(13),
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F5E9),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFA5D6A7)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline,
                        color: Color(0xFF2E7D32), size: 20),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Type the drug name and batch number as written on the package. Expiry is optional but improves accuracy.',
                        style:
                            TextStyle(fontSize: 12, color: Color(0xFF2E7D32)),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 22),

              // ── Drug name ─────────────────────────────────
              const Text('Medicine Name *',
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: Color(0xFF1A237E))),
              const SizedBox(height: 8),
              TextFormField(
                controller: _nameCtrl,
                decoration: _fieldDecor(
                    'e.g. Pantoprazole, Dolo 650, Amoxicillin',
                    Icons.medication),
                textCapitalization: TextCapitalization.words,
                validator: (v) {
                  if (v == null || v.trim().isEmpty) {
                    return 'Please enter a medicine name';
                  }
                  if (v.trim().length < 3) return 'Name too short';
                  return null;
                },
              ),
              const SizedBox(height: 18),

              // ── Batch ─────────────────────────────────────
              const Text('Batch Number (optional)',
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: Color(0xFF1A237E))),
              const SizedBox(height: 8),
              TextFormField(
                controller: _batchCtrl,
                decoration:
                    _fieldDecor('e.g. SP240165, AD-204', Icons.qr_code),
                textCapitalization: TextCapitalization.characters,
                validator: (v) {
                  // No longer mandatory
                  return null;
                },
              ),
              const SizedBox(height: 18),

              // ── Expiry ────────────────────────────────────
              const Text('Expiry Date (optional)',
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: Color(0xFF1A237E))),
              const SizedBox(height: 8),
              TextFormField(
                controller: _expCtrl,
                decoration: _fieldDecor(
                    'e.g. 05/2026 (MM/YYYY)', Icons.calendar_today),
                keyboardType: TextInputType.datetime,
              ),
              const SizedBox(height: 28),

              // ── Submit ────────────────────────────────────
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _loading ? null : _submit,
                  icon: _loading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                              color: Colors.white, strokeWidth: 2))
                      : const Icon(Icons.search),
                  label: Text(
                    _loading ? 'Checking…' : 'Check Drug Safety',
                    style: const TextStyle(
                        fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF2E7D32),
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: Colors.grey[300],
                    padding: const EdgeInsets.symmetric(vertical: 15),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // ── Quick examples ────────────────────────────
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.lightbulb_outline,
                              color: Colors.amber, size: 18),
                          SizedBox(width: 8),
                          Text('Tap to try an NSQ drug example:',
                              style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 13)),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: examples
                            .map(
                              (name) => GestureDetector(
                                onTap: () =>
                                    setState(() => _nameCtrl.text = name),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 10, vertical: 6),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFE8F5E9),
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(
                                        color: const Color(0xFFA5D6A7)),
                                  ),
                                  child: Text(name,
                                      style: const TextStyle(
                                          fontSize: 12,
                                          color: Color(0xFF2E7D32),
                                          fontWeight: FontWeight.w500)),
                                ),
                              ),
                            )
                            .toList(),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
