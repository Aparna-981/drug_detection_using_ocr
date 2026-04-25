import 'dart:io' as io;
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../services/api_service.dart';
import 'login_screen.dart';

class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key});

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  int _currentIndex = 0;
  io.File?   _datasetFile;
  Uint8List? _fileBytes;
  String?    _fileName;
  
  bool    _uploading   = false;
  bool    _uploadOk    = false;
  String? _uploadMsg;
  Map<String, dynamic>? _info;
  List<dynamic> _pendingUsers = [];
  List<dynamic> _allUsers = [];
  bool _loadingUsers = false;
  bool _loadingAllUsers = false;

  // Search state
  final _searchController = TextEditingController();
  List<dynamic> _searchResults = [];
  bool _searching = false;

  @override
  void initState() {
    super.initState();
    _loadInfo();
  }

  Future<void> _loadInfo() async {
    final i = await ApiService.getDatasetInfo();
    setState(() => _info = i);
    _loadPendingUsers();
    _loadAllUsers();
  }

  Future<void> _loadPendingUsers() async {
    setState(() => _loadingUsers = true);
    final users = await ApiService.getPendingUsers();
    setState(() {
      _pendingUsers = users;
      _loadingUsers = false;
    });
  }

  Future<void> _loadAllUsers() async {
    setState(() => _loadingAllUsers = true);
    final users = await ApiService.getAllUsers();
    setState(() {
      _allUsers = users;
      _loadingAllUsers = false;
    });
  }

  Future<void> _handleUserAction(int id, bool approve) async {
    final success = approve 
      ? await ApiService.approveUser(id) 
      : await ApiService.rejectUser(id);
    
    if (success) {
      _loadPendingUsers();
      _loadAllUsers();
    }
  }

  Future<void> _doSearch() async {
    final q = _searchController.text.trim();
    if (q.isEmpty) {
      setState(() => _searchResults = []);
      return;
    }
    setState(() => _searching = true);
    final results = await ApiService.searchDrugs(q);
    setState(() {
      _searchResults = results;
      _searching = false;
    });
  }

  Future<void> _pickFile() async {
    final r = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'xlsx', 'xls'],
    );
    if (r != null) {
      if (kIsWeb) {
        setState(() {
          _fileBytes = r.files.single.bytes;
          _fileName  = r.files.single.name;
          _uploadMsg = null;
        });
      } else if (r.files.single.path != null) {
        setState(() {
          _datasetFile = io.File(r.files.single.path!);
          _fileName    = r.files.single.name;
          _uploadMsg = null;
        });
      }
    }
  }

  Future<void> _upload() async {
    if (_datasetFile == null && _fileBytes == null) return;
    setState(() {
      _uploading = true;
      _uploadMsg = null;
    });

    try {
      final result = await ApiService.uploadDataset(
        kIsWeb ? _fileBytes : _datasetFile,
        _fileName ?? 'dataset.pdf',
      );
      setState(() {
        _uploadOk  = result['status'] == 'success' || result['status'] == 'partial';
        _uploadMsg = result['message'] as String? ?? result['error'];
      });
      await _loadInfo();
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F7FF),
      appBar: AppBar(
        elevation: 0,
        backgroundColor: const Color(0xFF6A1B9A),
        foregroundColor: Colors.white,
        title: const Text('Admin Dashboard',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        actions: [
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
      body: IndexedStack(
        index: _currentIndex,
        children: [
          _buildOverviewTab(),
          _buildSearchTab(),
          _buildUsersTab(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (idx) => setState(() => _currentIndex = idx),
        selectedItemColor: const Color(0xFF6A1B9A),
        unselectedItemColor: Colors.grey,
        type: BottomNavigationBarType.fixed,
        selectedLabelStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
        unselectedLabelStyle: const TextStyle(fontSize: 12),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: 'Overview'),
          BottomNavigationBarItem(icon: Icon(Icons.search_rounded), label: 'Search'),
          BottomNavigationBarItem(icon: Icon(Icons.people_alt_rounded), label: 'Users'),
        ],
      ),
    );
  }

  // ── HELPERS ───────────────────────────────────────────────

  Widget _buildStatCard(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: color.withOpacity(0.05), blurRadius: 10, offset: const Offset(0, 4))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(10)),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(height: 12),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 20, color: Color(0xFF1A237E))),
          Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[600], fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _buildEmptyCard(String msg, IconData icon) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(30),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          Icon(icon, size: 40, color: Colors.grey[200]),
          const SizedBox(height: 12),
          Text(msg, textAlign: TextAlign.center, style: TextStyle(color: Colors.grey[400], fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildUserActionCard(dynamic u) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: const CircleAvatar(backgroundColor: Color(0xFFE8EAF6), child: Icon(Icons.person_pin, color: Color(0xFF3F51B5))),
        title: Text(u['username'] ?? 'Unknown', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        subtitle: Text('Requested: ${u['created_at'].toString().split('T')[0]}', style: const TextStyle(fontSize: 12)),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(icon: const Icon(Icons.check_circle_rounded, color: Colors.green), onPressed: () => _handleUserAction(u['id'], true)),
            IconButton(icon: const Icon(Icons.cancel_rounded, color: Colors.red), onPressed: () => _handleUserAction(u['id'], false)),
          ],
        ),
      ),
    );
  }

  Widget _buildUserListCard(dynamic u) {
    final approved = u['is_approved'] == 1;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: Colors.grey[100]!)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: approved ? Colors.green[50] : Colors.orange[50], 
          child: Icon(approved ? Icons.verified_user_rounded : Icons.pending_actions_rounded, 
                      color: approved ? Colors.green : Colors.orange, size: 18),
        ),
        title: Text(u['username'] ?? 'User', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        subtitle: Text('Role: ${u['role']} • ${u['created_at'].toString().split('T')[0]}', style: const TextStyle(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(color: approved ? Colors.green[50] : Colors.orange[50], borderRadius: BorderRadius.circular(20)),
          child: Text(approved ? 'ACTIVE' : 'PENDING', 
                      style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: approved ? Colors.green[700] : Colors.orange[700])),
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String? value) {
    if (value == null || value == 'null') return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 90, child: Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[600], fontWeight: FontWeight.bold))),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 12, color: Color(0xFF1A237E)))),
        ],
      ),
    );
  }

  // Placeholder methods for upcoming phases
  Widget _buildOverviewTab() {
    final loaded = _info?['loaded'] as bool? ?? false;
    final count  = _info?['drug_count'] as int? ?? 0;
    final users  = _info?['total_users'] as int? ?? 0;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: _buildStatCard('Drugs Loaded', '$count', Icons.storage_rounded, Colors.purple)),
              const SizedBox(width: 12),
              Expanded(child: _buildStatCard('Total Users', '$users', Icons.people_outline_rounded, Colors.blue)),
            ],
          ),
          const SizedBox(height: 24),
          const Text('Dataset Management', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Color(0xFF1A237E))),
          const SizedBox(height: 12),
          Card(
            elevation: 2,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(loaded ? Icons.check_circle_rounded : Icons.info_rounded, color: loaded ? Colors.green : Colors.orange, size: 20),
                      const SizedBox(width: 10),
                      Text(loaded ? 'CDSCO Alert Data Live' : 'Database Empty', 
                           style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: loaded ? Colors.green[700] : Colors.orange[700])),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const Text('Select the monthly CDSCO NSQ Alert PDF or Excel to update the cross-check database.', 
                               style: TextStyle(fontSize: 13, color: Colors.grey, height: 1.4)),
                  const SizedBox(height: 20),
                  GestureDetector(
                    onTap: _pickFile,
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF8F9FE),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: (_datasetFile != null || _fileBytes != null) ? const Color(0xFF6A1B9A) : Colors.grey[200]!, width: 2),
                      ),
                      child: (_datasetFile != null || _fileBytes != null)
                          ? Row(children: [
                              Icon(
                                (_fileName?.toLowerCase().endsWith('.pdf') ?? false) ? Icons.picture_as_pdf_rounded : Icons.table_view_rounded,
                                color: (_fileName?.toLowerCase().endsWith('.pdf') ?? false) ? Colors.red : Colors.green[700],
                                size: 32
                              ),
                              const SizedBox(width: 12),
                              Expanded(child: Text(_fileName ?? 'Selected File', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13), maxLines: 1, overflow: TextOverflow.ellipsis)),
                              const Icon(Icons.edit_rounded, size: 16, color: Colors.grey),
                            ])
                          : Column(children: [
                               Icon(Icons.add_circle_outline_rounded, size: 40, color: Colors.grey[300]),
                               const SizedBox(height: 8),
                               const Text('Click to choose File (PDF/Excel)', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey, fontSize: 13)),
                             ]),
                    ),
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: ((_datasetFile != null || _fileBytes != null) && !_uploading) ? _upload : null,
                      icon: _uploading ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) : const Icon(Icons.upload_rounded, size: 18),
                      label: Text(_uploading ? 'Processing...' : 'Upload & Sync Database', style: const TextStyle(fontWeight: FontWeight.bold)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF6A1B9A),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        elevation: 0,
                      ),
                    ),
                  ),
                  if (_uploadMsg != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(color: _uploadOk ? Colors.green[50] : Colors.red[50], borderRadius: BorderRadius.circular(12), border: Border.all(color: _uploadOk ? Colors.green[200]! : Colors.red[200]!)),
                      child: Text(_uploadMsg!, textAlign: TextAlign.center, style: TextStyle(color: _uploadOk ? Colors.green[800] : Colors.red[800], fontSize: 12, fontWeight: FontWeight.bold)),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          const _InstructionsCard(),
          const SizedBox(height: 40),
        ],
      ),
    );
  }

  Widget _buildSearchTab() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          color: Colors.white,
          child: TextField(
            controller: _searchController,
            onSubmitted: (_) => _doSearch(),
            decoration: InputDecoration(
              hintText: 'Search by drug name or batch...',
              prefixIcon: const Icon(Icons.search_rounded, color: Color(0xFF6A1B9A)),
              suffixIcon: IconButton(icon: const Icon(Icons.send_rounded), onPressed: _doSearch),
              filled: true,
              fillColor: const Color(0xFFF4F7FF),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
              contentPadding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
        ),
        Expanded(
          child: _searching
            ? const Center(child: CircularProgressIndicator())
            : _searchResults.isEmpty
              ? Center(child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.search_off_rounded, size: 64, color: Colors.grey[300]),
                    const SizedBox(height: 16),
                    Text('No search results found', style: TextStyle(color: Colors.grey[400], fontWeight: FontWeight.bold)),
                  ],
                ))
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                  itemCount: _searchResults.length,
                  itemBuilder: (context, i) {
                    final d = _searchResults[i];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      child: ExpansionTile(
                        leading: Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(color: const Color(0xFFF3E5F5), borderRadius: BorderRadius.circular(8)),
                          child: const Icon(Icons.medication, color: Color(0xFF6A1B9A), size: 20),
                        ),
                        title: Text(d['drug_name'] ?? 'Unknown', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                        subtitle: Text('Batch: ${d['batch_no'] ?? 'N/A'}', style: const TextStyle(fontSize: 12)),
                        childrenPadding: const EdgeInsets.all(16),
                        expandedCrossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildDetailRow('Manufacturer', d['manufactured_by']),
                          _buildDetailRow('Expiry', d['expiry_date']),
                          _buildDetailRow('NSQ Reason', d['nsq_result']),
                          _buildDetailRow('Lab Details', d['lab']),
                          _buildDetailRow('Alert Month', d['alert_month']),
                        ],
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildUsersTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Pending Approvals', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Color(0xFF1A237E))),
          const SizedBox(height: 12),
          if (_loadingUsers)
            const Center(child: Padding(padding: EdgeInsets.all(20), child: CircularProgressIndicator()))
          else if (_pendingUsers.isEmpty)
            _buildEmptyCard('No registration requests pending.', Icons.person_add_disabled)
          else
            ..._pendingUsers.map((u) => _buildUserActionCard(u)),
          const SizedBox(height: 30),
          const Text('System Members', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Color(0xFF1A237E))),
          const SizedBox(height: 12),
          if (_loadingAllUsers)
            const Center(child: Padding(padding: EdgeInsets.all(20), child: CircularProgressIndicator()))
          else
            ..._allUsers.map((u) => _buildUserListCard(u)),
          const SizedBox(height: 40),
        ],
      ),
    );
  }
}

class _InstructionsCard extends StatelessWidget {
  const _InstructionsCard();
  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      color: const Color(0xFFF3E5F5),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(children: [
              Icon(Icons.lightbulb_outline_rounded, color: Color(0xFF6A1B9A), size: 20),
              SizedBox(width: 8),
              Text('Monthly Manual Update', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF6A1B9A), fontSize: 14)),
            ]),
            const SizedBox(height: 10),
            Text('To sync the latest alerts, visit cdsco.gov.in, download the Monthly NSQ PDF or create an Excel list, and upload it here.',
                 style: TextStyle(fontSize: 12, color: Colors.purple[800], height: 1.5)),
          ],
        ),
      ),
    );
  }
}
