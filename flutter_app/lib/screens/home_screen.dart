import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'scan_screen.dart';
import 'manual_screen.dart';
import 'admin_screen.dart';
import 'login_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _checking    = true;
  bool _serverOnline = false;
  int  _drugCount   = 0;
  String _ocrEngine = '';

  @override
  void initState() {
    super.initState();
    _checkServer();
  }

  Future<void> _checkServer() async {
    setState(() => _checking = true);
    final info = await ApiService.checkHealth();
    setState(() {
      _checking     = false;
      _serverOnline = info['status'] == 'ok';
      _drugCount    = info['drug_count'] as int? ?? 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1565C0),
        foregroundColor: Colors.white,
        title: const Text('Drug Safety Checker',
            style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: _checking
                ? const Center(
                    child: SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                          color: Colors.white, strokeWidth: 2),
                    ),
                  )
                : Row(
                    children: [
                      Icon(
                        _serverOnline ? Icons.cloud_done : Icons.cloud_off,
                        size: 18,
                        color: _serverOnline
                            ? Colors.greenAccent
                            : Colors.redAccent,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        _serverOnline ? 'Online' : 'Offline',
                        style: TextStyle(
                          fontSize: 12,
                          color: _serverOnline
                              ? Colors.greenAccent
                              : Colors.redAccent,
                        ),
                      ),
                    ],
                  ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh, size: 20),
            onPressed: _checkServer,
            tooltip: 'Re-check server',
          ),
          IconButton(
            icon: const Icon(Icons.logout, size: 20),
            onPressed: () => Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => const LoginScreen()),
            ),
            tooltip: 'Logout',
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Hero banner ────────────────────────────────
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF1565C0), Color(0xFF42A5F5)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.health_and_safety,
                      color: Colors.white, size: 44),
                  const SizedBox(height: 12),
                  const Text(
                    'Smart Drug\nDetection System',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      height: 1.3,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Scan medicine packages to instantly check\nif they are NSQ-flagged or expired.',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.85),
                      fontSize: 13,
                      height: 1.5,
                    ),
                  ),
                  if (_serverOnline) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.18),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '🔬 $_ocrEngine  •  $_drugCount drugs in database',
                        style: const TextStyle(
                            color: Colors.white, fontSize: 12),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 20),

            // ── Offline warning ────────────────────────────
            if (!_serverOnline && !_checking) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFEBEE),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: Colors.redAccent.withOpacity(0.4)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded,
                        color: Colors.red, size: 22),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Text(
                        'Backend server is offline.\nPlease start the Python server first.',
                        style: TextStyle(color: Colors.red, fontSize: 13),
                      ),
                    ),
                    TextButton(
                      onPressed: _checkServer,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
            ],

            // ── Section header ─────────────────────────────
            const Text('What would you like to do?',
                style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF1A237E))),
            const SizedBox(height: 14),

            // ── Scan card ──────────────────────────────────
            _ActionCard(
              icon: Icons.camera_alt_rounded,
              title: 'Scan Medicine',
              subtitle:
                  'Take a photo of the package',
              color: const Color(0xFF1565C0),
              onTap: _serverOnline
                  ? () => Navigator.push(context,
                      MaterialPageRoute(builder: (_) => const ScanScreen()))
                  : null,
            ),
            const SizedBox(height: 12),

            const SizedBox(height: 12),
            _ActionCard(
              icon: Icons.edit_note_rounded,
              title: 'Manual Entry',
              subtitle: 'Type the drug name to check if it is in the NSQ list',
              color: const Color(0xFF2E7D32),
              onTap: _serverOnline
                  ? () => Navigator.push(context,
                      MaterialPageRoute(builder: (_) => const ManualScreen()))
                  : null,
            ),
            const SizedBox(height: 28),

            // ── How it works ───────────────────────────────
            const Text('How It Works',
                style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF1A237E))),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    for (final step in const [
                      ('1', 'Scan',    'Take a photo of the medicine package'),
                      ('2', 'Extract', 'PaddleOCR reads drug name, batch & expiry'),
                      ('3', 'Match',   'Fuzzy-matched against the NSQ database'),
                      ('4', 'Result',  'Instant safe / NSQ / expired alert'),
                    ])
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Row(
                          children: [
                            CircleAvatar(
                              radius: 13,
                              backgroundColor: const Color(0xFF1565C0),
                              child: Text(step.$1,
                                  style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold)),
                            ),
                            const SizedBox(width: 12),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(step.$2,
                                    style: const TextStyle(
                                        fontWeight: FontWeight.bold,
                                        fontSize: 13)),
                                Text(step.$3,
                                    style: TextStyle(
                                        fontSize: 12,
                                        color: Colors.grey[600])),
                              ],
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }
}

// ── Reusable action card ───────────────────────────────────────
class _ActionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final VoidCallback? onTap;

  const _ActionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final active = onTap != null;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: active
                      ? color.withOpacity(0.1)
                      : Colors.grey.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: Icon(icon,
                    color: active ? color : Colors.grey, size: 26),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: active
                                ? const Color(0xFF1A237E)
                                : Colors.grey)),
                    const SizedBox(height: 3),
                    Text(subtitle,
                        style: TextStyle(
                            fontSize: 12,
                            color: active
                                ? Colors.grey[600]
                                : Colors.grey[400],
                            height: 1.4)),
                  ],
                ),
              ),
              Icon(Icons.arrow_forward_ios,
                  color: active ? color : Colors.grey[300], size: 15),
            ],
          ),
        ),
      ),
    );
  }
}
