"""
目标代码结构定义文件
定义了重构后代码的类和方法结构
"""

class Config:
    - min_size
    - white_threshold
    - white_score_threshold
    - similarity_level
    - max_workers
    - use_multithreading
    - exclude_paths
    - artbook_keywords
    - handle_artbooks
    - filter_height_enabled
    - filter_white_enabled
    - remove_duplicates
    - bak_mode
    - backup_removed_files_enabled
    - add_processed_comment_enabled
    - add_processed_log_enabled
    - ignore_yaml_log
    - ignore_processed_log
    - processed_files_yaml
    - load_config()
    - get_thread_count()
    - get_batch_size()
    - default_thread_count()
    - default_batch_size()

class Logger:
    - setup_logger()
    - log_verbose()
    - print_config()
    - generate_summary_report()
    - handle_file_error()
    - handle_archive_error()
    - handle_image_error()
    - print_tree_structure()

class PathManager:
    - ensure_long_path()
    - safe_file_op()
    - create_temp_directory()
    - cleanup_temp_files()
    - get_directory_stats()
    - check_and_rename_long_filename()
    - shorten_filename()
    - restore_filename()
    - load_filename_mapping()
    - save_filename_mapping()
    - generate_encryption_key()

class ImageAnalyzer:
    - is_greyscale()
    - calculate_white_score_fast()
    - calculate_grayscale_score()
    - check_image_quality()
    - check_white_score()
    - check_image_size()
    - verify_image_with_vips()

class ImageProcessor:
    - process_image_in_memory()
    - process_single_image()
    - process_images()
    - process_images_in_directory()
    - get_optimal_thread_count()
    - configure_image_conversion()
    - configure_lossless_mode()

class DuplicateDetector:
    - calculate_image_hash()
    - remove_duplicates_in_memory()
    - compare_images()

class FileNameHandler:
    - decode_japanese_filename()
    - try_decoding_with_multiple_encodings()
    - get_image_files()
    - check_file_type()
    - is_supported_format()

class DirectoryHandler:
    - remove_empty_directories()
    - flatten_single_subfolder()
    - remove_files()
    - restore_files()
    - get_file_list()
    - scan_directory()
    - create_directory()
    - ensure_directory()

class ArchiveExtractor:
    - prepare_archive()
    - extract_file_from_zip()
    - read_zip_contents()
    - extract_archive()
    - verify_extraction()
    - check_archive_contents()

class ArchiveCompressor:
    - create_new_archive()
    - create_new_zip()
    - run_7z_command()
    - compress_directory()
    - verify_compression()
    - optimize_compression()

class ArchiveProcessor:
    - process_archive_in_memory()
    - process_single_archive()
    - merge_archives()
    - split_merged_archive()
    - handle_size_comparison()
    - is_archive_valid()
    - cleanup_and_compress()

class ProcessedLogHandler:
    - add_processed_log()
    - has_processed_log()
    - load_processed_files()
    - save_processed_file()
    - update_processed_log()
    - check_processed_status()

class BackupHandler:
    - backup_removed_files()
    - backup_files_to_dir()
    - restore_bak_files()
    - handle_bak_file()
    - delete_backup_if_successful()
    - create_backup()
    - verify_backup()

class ContentFilter:
    - is_artbook()
    - should_process_file()
    - is_excluded_path()
    - check_archive_size()
    - check_content_type()
    - apply_filters()

class ProgressTracker:
    - update_current_archive()
    - update_status()
    - update_current_task()
    - increment_overall()
    - set_total_archives()
    - update_overall_progress()
    - add_log()
    - create_result_dict()
    - _should_update()

class InputHandler:
    - get_input_paths()
    - validate_args()
    - parse_arguments()
    - prepare_params()
    - get_paths_from_clipboard()
    - validate_paths()
    - check_input_type()

class ProcessManager:
    - process_all_archives()
    - process_directory()
    - process_merged_archives()
    - process_normal_archives()
    - handle_restore_mode()
    - monitor_directories()
    - auto_run_process()
    - check_pending_files()
    - _process_file()

class Application:
    - initialize()
    - run()
    - cleanup()
    - main()
    - init_performance_config()
    - init_keywords()
    - start()
    - stop() 