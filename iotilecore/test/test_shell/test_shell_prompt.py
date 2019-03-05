from iotile.core.scripts.iotile_script import main


class TestShellPrompt:
    """Used for testing shell prompt.
        TestShellPrompt uses monkeypatch.setattr to change default 'input' function to another one(my_input).
        Note: first arguments in monkeypatch.setattr must be path to 'input' function inside module with 'main' function
            and second must be your own function"""
    main_input = ''

    def my_input(self, input):
        """Overrides 'input' function inside 'main' function
            Note: It should always send exit command """
        self.main_input = input  # saving input text
        # sending exit command to the shell after using input
        return "quit"

    def test_prompt(self, monkeypatch):
        """Make sure we can change prompt."""
        monkeypatch.setattr('iotile.core.scripts.iotile_script.input', self.my_input)

        main(['-p', '{context} 123'])
        assert self.main_input == 'root 123'

        main(['-p', '{{context}}'])
        assert self.main_input == '{{context}}'

        main(['-p', '({context}) '])
        assert self.main_input == '(root) '

        main()
        assert self.main_input == '(root) '
